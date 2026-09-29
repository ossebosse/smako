"""Official per-store current publication discovery; no fixed store/week/PDF."""
import hashlib
import json
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import httpx
from bs4 import BeautifulSoup


def publication_links(html, store):
    fields = store["source_fields"]
    official = urlsplit(fields["official_store_url"])
    if official.scheme != "https" or official.hostname != "x-tra.se" or not official.path.startswith("/butiker/"):
        raise ValueError("unverified official X:-tra store page")
    soup = BeautifulSoup(html,"html.parser")
    raw = json.loads(soup.find("script",id="__NEXT_DATA__").string)["props"]["pageProps"]["data"]["store"]
    if (str(raw["id"]) != store["external_id"]
            or str(raw["ledgerAccountNumber"]) != fields["ledger_account_number"]
            or raw.get("streetName") != store["address"] or raw.get("city") != store["city"]):
        raise ValueError("official store identity/address changed")
    visible = {a.get("href") for a in soup.select("a[href]")}
    current = raw.get("weeklyOffersLink")
    if not current:
        raise ValueError("current publication field missing from official store page")
    links = {current} | {u for u in visible if urlsplit(u).hostname == "dr.coop.se"}
    for url in links:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.username or parsed.password
                or parse_qs(parsed.query).get("store") != [fields["ledger_account_number"]]):
            raise ValueError("publication link not bound to this store")
    return sorted(links)


async def fetch_publications(row, output):
    """Fresh page -> actual linked bytes. Unexpected redirects/formats stay blocked."""
    import pymupdf

    output.mkdir(parents=True,exist_ok=False)
    store=row["store"];url=store["source_fields"]["official_store_url"]
    result={"store_id":store["external_id"],"official_store_url":url,"editions":[],
            "complete":False,"completeness_reason":"only publications linked by this official page; text ads remain partial"}
    async with httpx.AsyncClient(timeout=30,follow_redirects=False) as client:
        response=await client.get(url);response.raise_for_status()
        raw_store=json.loads(BeautifulSoup(response.text,"html.parser").find("script",id="__NEXT_DATA__").string)["props"]["pageProps"]["data"]["store"]
        (output/"store-page.json").write_text(json.dumps({"source_url":url,"sha256":hashlib.sha256(response.content).hexdigest(),
            "observed_at":datetime.now(UTC).isoformat(),"field_path":"props.pageProps.data.store.weeklyOffersLink","store":raw_store},ensure_ascii=False,indent=2),encoding="utf8")
        links=publication_links(response.text,store)
        result.update(store_page_sha256=hashlib.sha256(response.content).hexdigest(),
                      store_page_observed_at=datetime.now(UTC).isoformat(),discovered_links=links)
        for number,link in enumerate(links,1):
            folder=output/str(number);folder.mkdir()
            meta={"store_id":store["external_id"],"source_url":link,"status":"unknown"}
            try:
                async with client.stream("GET",link) as document:
                    document.raise_for_status();payload=bytearray()
                    async for chunk in document.aiter_bytes():
                        payload.extend(chunk)
                        if len(payload)>20_000_000:raise ValueError("document exceeds size limit")
                observed=datetime.now(UTC).isoformat()
                if not payload.startswith(b"%PDF"):raise ValueError("linked publication is not supported PDF")
                (folder/"source.pdf").write_bytes(payload)
                with pymupdf.open(stream=payload,filetype="pdf") as pdf:
                    pages=pdf.page_count;has_text=any(p.get_text().strip() for p in pdf)
                meta.update(status="text_ready" if has_text else "image_dependent",sha256=hashlib.sha256(payload).hexdigest(),
                            observed_at=observed,document_pages=pages,pages_read=pages,
                            store_page_sha256=result["store_page_sha256"])
            except (httpx.HTTPError,ValueError,RuntimeError) as exc:
                meta.update(status="blocked_publication",error_type=type(exc).__name__,reason=str(exc)[:300])
            (folder/"result.json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf8")
            result["editions"].append({**meta,"directory":str(folder)})
    (output/"publications.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf8")
    return result
