"""Bounded X:-tra PDF text-layout adapter. No OCR, images or fabricated SKU.

Versioned typography/grid recognition; all detected textual ads retained.
Unknown picture-only content means overall advertisement completeness is unknown.
Source price identity is an opaque document/ad ID, never a claimed retailer GTIN.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from urllib.parse import parse_qs, urlsplit

import pymupdf

from grocery_data.app.connectors.coop.connector import CoopRowApprovedOfferConnector
from grocery_data.app.domain import ParseFailure, ProductParseResult, SourceOffer, SourceProduct

POLICY = "coop-xtra-pdf-text-v1"
PARSER = "xtra-pdf-text-v2"


def _money(s):
    return Decimal(s.replace(":-", "").replace(":", ".").replace(",", "."))


def _unique(spans):
    result = []
    seen = set()
    for s in spans:
        key = (s["text"], tuple(round(v, 1) for v in s["bbox"]), round(s["size"], 1))
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result


def read_layout(pdf):
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        pages = []
        for i, page in enumerate(doc):
            spans = []
            for block in page.get_text("dict")["blocks"]:
                if block["type"] != 0:
                    continue
                for line in block["lines"]:
                    for s in line["spans"]:
                        spans.append(
                            {
                                "id": len(spans),
                                "block": block["number"],
                                **{k: s[k] for k in ["text", "bbox", "size", "font", "origin"]},
                            }
                        )
            pages.append(
                {
                    "page": i + 1,
                    "width": page.rect.width,
                    "height": page.rect.height,
                    "spans": spans,
                    "images": len(page.get_images()),
                }
            )
        return doc.metadata, pages


def bound_period(metadata, pages, store, document):
    fields = store.source_fields
    link = fields.get("offers_url", "")
    url = urlsplit(link)
    if (
        fields.get("concept") != "X:-tra"
        or not store.address
        or url.scheme != "https"
        or url.hostname != "dr.coop.se"
        or parse_qs(url.query).get("store") != [str(fields.get("ledger_account_number"))]
        or document.url != link
        or document.store_external_id != store.external_id
        or document.payload_hash != fields.get("pdf_sha256")
        or document.fetched_at.isoformat() != fields.get("pdf_observed_at")
        or not fields.get("official_store_url", "").startswith("https://x-tra.se/butiker/")
        or store.name.casefold() not in metadata.get("title", "").casefold()
    ):
        raise ValueError("PDF/store/link/hash/observation evidence mismatch")
    year = int(re.fullmatch(r"D:(\d{4})\d{10}.*", metadata["creationDate"])[1])
    headers = " ".join(s["text"] for s in pages[0]["spans"])
    m = re.search(r"v\.(\d{1,2}),\s*(\d{1,2})/(\d{1,2})[–-](\d{1,2})/(\d{1,2})", headers)
    if not m:
        raise ValueError("explicit campaign period missing")
    start, end = date(year, int(m[3]), int(m[2])), date(year, int(m[5]), int(m[4]))
    if start > end or start.isocalendar().week != int(m[1]):
        raise ValueError("campaign week/date mismatch")
    for p in pages:
        editions = re.findall(r"cx_(\d{2})(\d{2})_[^\s]+", " ".join(s["text"] for s in p["spans"]))
        if editions != [(str(year)[2:], m[1].zfill(2))]:
            raise ValueError("page edition missing or disagrees with period")
    return start, end


def page_ads(page, start, end):
    spans = _unique(page["spans"])
    # A style contract, not a product list. Reject changed or ambiguous layouts.
    titles = [
        s
        for s in spans
        if s["font"] == "ProximaNovaCond-Extrabld"
        and 9.5 <= s["size"] <= 10.5
        and re.search("[A-Za-zÅÄÖåäö]", s["text"])
    ]
    titles.sort(key=lambda s: (round(s["bbox"][1] / 6), s["bbox"][0]))
    groups = []
    for title in titles:
        group = next((g for g in groups if abs(g[0]["bbox"][1] - title["bbox"][1]) < 6), None)
        if group is None:
            groups.append([title])
        else:
            group.append(title)
    prices = [
        s
        for s in spans
        if s["font"] == "ProximaNovaCond-Extrabld"
        and s["size"] >= 45
        and re.fullmatch(r"\d+", s["text"].strip())
    ]
    prices = [
        s
        for s in prices
        if not any(
            h["size"] > s["size"] * 1.4
            and abs(s["bbox"][0] - h["bbox"][2]) < 5
            and 0.1 * h["size"] < s["bbox"][1] - h["bbox"][1] < 0.5 * h["size"]
            for h in prices
        )
    ]
    page_text = " ".join(s["text"] for s in spans if s["bbox"][1] < 190)
    specific = re.search(
        r"Gäller endast\s+\w+\s+(\d{1,2})/(\d{1,2})\s*[–-]\s*\w+\s+(\d{1,2})/(\d{1,2})", page_text
    )
    if "Gäller endast" in page_text and not specific:
        return [], {
            "shared_blocker": "page_validity_unparsed",
            "unclassified_price_spans": [p["id"] for p in prices],
        }
    if specific:
        start = max(start, date(start.year, int(specific[2]), int(specific[1])))
        end = min(end, date(end.year, int(specific[4]), int(specific[3])))
    ads = []
    used = set()
    condition_used = set()
    conditions = [s for s in spans if "Medlemspris" in s["text"]]
    for gi, group in enumerate(groups):
        group.sort(key=lambda s: s["bbox"][0])
        previous_y = max((max(t["bbox"][3] for t in g) for g in groups[:gi]), default=0)
        for ti, title in enumerate(group):
            x, y = title["bbox"][:2]
            left = x - 30
            right = group[ti + 1]["bbox"][0] - 30 if ti + 1 < len(group) else page["width"] - 15
            body = [
                s
                for s in spans
                if s["font"] in {"ProximaNovaCond-Regular", "ProximaNovaCond-Bold"}
                and 7 <= s["size"] <= 8.6
                and y - 1 <= s["bbox"][1] <= y + 48
                and left <= (s["bbox"][0] + s["bbox"][2]) / 2 < right
            ]
            body.sort(key=lambda s: (round(s["origin"][1], 1), s["bbox"][0]))
            text = " ".join(s["text"].strip() for s in body)
            candidates = [
                s
                for s in prices
                if left <= (s["bbox"][0] + s["bbox"][2]) / 2 < right
                and previous_y < s["bbox"][1] < y
                and y - s["bbox"][1] < 210
            ]
            blockers = []
            amount = None
            unit = None
            quantity = 1
            member = False
            price_spans = []
            if len(candidates) != 1:
                blockers.append("price_column_row_assignment_ambiguous")
            else:
                head = candidates[0]
                used.add(head["id"])
                price_spans = [head]
                suffix = [
                    s
                    for s in spans
                    if s["font"] == head["font"]
                    and (re.fullmatch(r"\d{2}", s["text"].strip()) or s["text"].strip() == ":-")
                    and 0.3 < head["size"] ** -1 * s["size"] < 0.7
                    and abs(s["bbox"][0] - head["bbox"][2]) < 5
                    and 0.1 * head["size"] < s["bbox"][1] - head["bbox"][1] < 0.5 * head["size"]
                ]
                if len(suffix) != 1:
                    blockers.append("price_fraction_ambiguous")
                else:
                    price_spans += suffix
                    amount = _money(
                        head["text"].strip()
                        + (
                            "." + suffix[0]["text"].strip()
                            if suffix[0]["text"].strip() != ":-"
                            else ""
                        )
                    )
                nearby = [
                    s
                    for s in spans
                    if head["bbox"][0] - 40
                    <= s["bbox"][0]
                    <= max(v["bbox"][2] for v in price_spans) + 10
                    and head["bbox"][1] <= s["bbox"][1] < y
                ]
                groupset = {
                    int(m[1])
                    for s in nearby
                    if (m := re.fullmatch(r"(\d+) för", s["text"].strip()))
                }
                units = {
                    s["text"].strip()[1:]
                    for s in nearby
                    if re.fullmatch(r"/(st|kg|nät)", s["text"].strip()) and s["size"] > 6
                }
                if len(groupset) > 1 or len(units) > 1 or (groupset and units):
                    blockers.append("purchase_unit_or_group_ambiguous")
                elif groupset:
                    quantity = next(iter(groupset))
                    unit = "st"
                elif units:
                    unit = next(iter(units))
                else:
                    blockers.append("purchase_unit_missing")
                labels = [s for s in nearby if "Medlemspris" in s["text"]]
                member = bool(labels)
                condition_used.update(s["id"] for s in labels)
                price_spans += [
                    s
                    for s in nearby
                    if re.fullmatch(r"(\d+ för|/(st|kg|nät)|Medlemspris)", s["text"].strip())
                ]
            ads.append(
                {
                    "page": page["page"],
                    "ad": len(ads) + 1,
                    "title": title["text"].strip().rstrip("."),
                    "body": text,
                    "bbox": [
                        left,
                        previous_y,
                        right,
                        max([title["bbox"][3], *[s["bbox"][3] for s in body]]),
                    ],
                    "text_spans": [title, *body],
                    "price_spans": price_spans,
                    "purchase_price": str(amount) if amount is not None else None,
                    "sale_unit": unit,
                    "required_packages": quantity,
                    "member_only": member,
                    "valid_from": str(start),
                    "valid_to": str(end),
                    "blockers": blockers,
                }
            )
    unassigned_conditions = [s["id"] for s in conditions if s["id"] not in condition_used]
    linked = {s["id"] for a in ads for s in a["text_spans"]}
    unassigned_critical = [
        s["id"]
        for s in spans
        if s["id"] not in linked
        and s["size"] >= 7
        and re.search(r"\bMax\s+\d|\bpant\b|aktiver|personlig|kupong", s["text"], re.IGNORECASE)
    ]
    if unassigned_conditions:
        for ad in ads:
            ad["blockers"].append("unassigned_page_membership_condition")
    if unassigned_critical:
        for ad in ads:
            ad["blockers"].append("unassigned_page_critical_condition")
    return ads, {
        "unclassified_price_spans": [p["id"] for p in prices if p["id"] not in used],
        "unassigned_condition_spans": unassigned_conditions + unassigned_critical,
        "detected_text_ads": len(ads),
        "advertisement_completeness": "unknown_nontext_content_not_interpreted",
    }


def parse_pdf(document, store, reference):
    metadata, pages = read_layout(document.payload)
    try:
        start, end = bound_period(metadata, pages, store, document)
        if len(pages) != store.source_fields.get("pdf_pages"):
            raise ValueError("document page count disagrees with retained source")
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        return ProductParseResult(
            failures=[
                ParseFailure(
                    raw_record_reference=reference,
                    error_code="schema_changed",
                    error_message=str(exc),
                    parser_version=PARSER,
                )
            ]
        ), {"shared_blocker": str(exc), "pages": []}
    products = []
    report = {
        "document_sha256": document.payload_hash,
        "observed_at": document.fetched_at.isoformat(),
        "store_id": store.external_id,
        "source_url": document.url,
        "metadata": metadata,
        "valid_from": str(start),
        "valid_to": str(end),
        "pages": [],
        "complete": False,
    }
    shared_text = [
        {"page": p["page"], **s}
        for p in pages
        for s in p["spans"]
        if "hushåll och kan enbart" in s["text"]
        or "Lokala avvikelser" in s["text"]
        or "Våra erbjudanden för" in s["text"]
        or (s["bbox"][1] < 190 and "Gäller endast" in s["text"])
    ]
    for page in pages:
        ads, status = page_ads(page, start, end)
        for ad in ads:
            text = ad["body"]
            title = ad["title"]
            blockers = ad["blockers"]
            pack = re.search(
                r"(?<![\d,–-])(\d+(?:[.,]\d+)?)\s*(kg|g|ml|liter)\b", text, re.IGNORECASE
            )
            package = Decimal(pack[1].replace(",", ".")) if pack else None
            unit = pack[2].lower() if pack else None
            if unit in {"kg", "liter"}:
                package *= 1000
                unit = "g" if unit == "kg" else "ml"
            if not pack or re.search(
                r"\bca\b|\d+(?:[.,]\d+)?\s*[-–x]\s*\d+(?:[.,]\d+)?\s*(?:g|kg|ml|liter)",
                text,
                re.IGNORECASE,
            ):
                blockers.append("fixed_package_unverified")
                package, unit = None, None
            if (
                re.search(r"Välj mellan|olika sorter|Ord\. pris från \d", text, re.IGNORECASE)
                or "/" in title
            ):
                blockers.append("exact_advertised_variant_unverified")
            if re.search(r"pant", text, re.IGNORECASE):
                blockers.append("deposit_amount_unverified")
            if unit == "ml":
                blockers.append("container_deposit_applicability_unverified")
            if re.search(r"Gäller|endast|aktiver|personlig|kupong", text, re.IGNORECASE):
                blockers.append("additional_condition_requires_review")
            limit = re.search(r"Max\s+(\d+)\s+(st|köp)/hushåll", text, re.IGNORECASE)
            if "Max" in text and not limit:
                blockers.append("purchase_limit_unparsed")
            if limit and ad["member_only"]:
                # The footer makes these limits global across X:-tra stores.
                # A store-specific PDF hash cannot identify that shared campaign.
                blockers.append("shared_household_campaign_identity_unverified")
            if ad["sale_unit"] not in {"st", "nät"}:
                blockers.append("weight_price_not_supported_for_concrete_purchase")
            comparison = re.search(r"Jfr-pris\s+(\d+(?:[,:.]\d+)?|\d+:-)/(kg|liter)\b", text)
            # Independent consistency check of the assigned price and package.
            if (
                comparison
                and package
                and ad["purchase_price"]
                and (
                    (unit == "g" and comparison[2] == "kg")
                    or (unit == "ml" and comparison[2] == "liter")
                )
            ):
                actual = Decimal(ad["purchase_price"]) / ad["required_packages"] / (package / 1000)
                if abs(actual - _money(comparison[1])) > Decimal(".02"):
                    blockers.append("printed_comparison_conflicts_with_purchase")
            elif not comparison:
                blockers.append("independent_price_package_check_unavailable")
            elif package and ad["purchase_price"]:
                blockers.append("comparison_unit_basis_unverified")
            ad["reference_prices"] = re.findall(
                r"(?:Ord\. pris|Tidigare lägsta pris)[^.]*?(?:/st\.|/kg\.|/liter\.)", text
            )
            ad["comparison_text"] = re.findall(r"Jfr-pris[^.]*\.", text)
            ad["package_quantity"] = str(package) if package else None
            ad["package_unit"] = unit
            ad["purchase_limit"] = int(limit[1]) if limit else None
            ad["deposit_status"] = (
                "unknown"
                if "pant" in text.lower() or unit == "ml"
                else "not_indicated_nonbeverage_solid"
            )
            from grocery_data.app.domain.purchase_terms import PurchaseTerms
            terms_data = None
            open_group = ('exact_advertised_variant_unverified' in blockers
                          and ad['sale_unit'] in {'st', 'nät'})
            approximate = re.search(r'\bca\s+(\d+(?:[.,]\d+)?)\s*(g|kg)\b', text, re.IGNORECASE)
            variable = bool(ad['sale_unit']=='kg' and approximate and not open_group)
            loose = bool(ad['sale_unit']=='kg' and re.search(r'\blösvikt\b', text, re.IGNORECASE))
            if (variable or loose) and comparison and (comparison[2]!='kg' or _money(comparison[1]) != Decimal(ad['purchase_price'])):
                blockers.append('printed_weight_rate_conflict')
            removable = set()
            if open_group:
                removable |= {'exact_advertised_variant_unverified', 'fixed_package_unverified'}
            if variable or loose:
                removable |= {'fixed_package_unverified', 'weight_price_not_supported_for_concrete_purchase'}
            remaining = [b for b in blockers if b not in removable]
            if not remaining:
                approximate_g = float(Decimal(approximate[1].replace(',', '.')) * (1000 if approximate[2].lower()=='kg' else 1)) if variable else None
                terms_data = PurchaseTerms(source_reference=f"{reference}#page={ad['page']}&ad={ad['ad']}",
                    purchase_form='fixed_package' if open_group else 'variable_package' if variable else 'loose_weight' if loose else 'piece' if unit=='st' and package==1 else 'fixed_package',
                    identity_scope='campaign_group' if open_group else 'product',
                    variant_selection='required' if open_group else 'resolved',
                    complete_group_size=ad['required_packages'],
                    approximate_package_g=approximate_g,
                    quantity_basis='unknown' if open_group else 'source_approximation' if variable else 'requirement' if loose else 'source_exact',
                    limit_scope='household_campaign' if limit else 'offer').model_dump(mode='json')
                blockers[:] = remaining
            ad["blockers"] = sorted(set(blockers))
            identity = f"pdf:{document.payload_hash}:p{ad['page']}:ad{ad['ad']}"
            ad["source_product_id"] = identity
            ad["status"] = "blocked" if ad["blockers"] else "extracted_qualified"
            payload = {
                "policy": POLICY,
                "document_sha256": document.payload_hash,
                "source_url": document.url,
                "observed_at": document.fetched_at.isoformat(),
                "page": ad["page"],
                "ad": ad["ad"],
                "price_role": "member_purchase" if ad["member_only"] else "campaign_purchase",
                "advertisement": ad,
                "shared_text": shared_text,
                "price_contract_id": f"coop:household:xtra:{document.payload_hash}:p{ad['page']}:ad{ad['ad']}",
                **({'purchase_terms':terms_data, 'price_basis_unit':'kg' if variable or loose else 'package'} if terms_data else {}),
            }
            offers = (
                ()
                if not ad["purchase_price"]
                else (
                    SourceOffer(
                        external_id=identity,
                        type="multibuy"
                        if ad["required_packages"] > 1
                        else "member_price"
                        if ad["member_only"]
                        else "sale_price",
                        price=ad["purchase_price"],
                        quantity=ad["required_packages"] if ad["required_packages"] > 1 else None,
                        member_only=ad["member_only"],
                        max_quantity=ad["purchase_limit"],
                        valid_from=ad["valid_from"],
                        valid_to=ad["valid_to"],
                        description=title + "; " + text,
                        source_payload=payload,
                    ),
                )
            )
            products.append(
                SourceProduct(
                    chain="coop",
                    store_external_id=store.external_id,
                    external_product_id=identity,
                    name=title,
                    brand=text.split(".")[0] if text else None,
                    package_text=pack[0] if pack else None,
                    package_quantity=package,
                    package_unit=unit,
                    sale_unit="st" if ad["sale_unit"] == "nät" else ad["sale_unit"],
                    offers=offers,
                    raw_reference=f"{reference}#page={ad['page']}&ad={ad['ad']}",
                    fetched_at=document.fetched_at,
                    basket_type="VIKT" if loose else "ST",
                    average_weight_kg=Decimal(str(approximate_g))/1000 if variable and terms_data else None,
                    source_fields={
                        "coop_physical_policy": POLICY,
                        "verified_store_scope": True,
                        **({'purchase_terms':terms_data} if terms_data else {}),
                        "variant_count": 1
                        if "exact_advertised_variant_unverified" not in blockers
                        else None,
                        "source_variant_id": identity,
                        "purchase_blockers": ad["blockers"],
                        "pdf_text_evidence": {
                            "document_sha256": document.payload_hash,
                            "page": ad["page"],
                            "ad": ad["ad"],
                        },
                    },
                )
            )
        report["pages"].append({"page": page["page"], **status, "ads": ads})
    return ProductParseResult(products=products), report


def row_evidence_matches(product, store):
    """Do not let the text-policy marker stand in for a bound price contract."""
    try:
        offer = product.offers[0]
        payload = offer.source_payload
        ad = payload["advertisement"]
        digest = store.source_fields["pdf_sha256"]
        return (
            len(product.offers) == 1
            and payload["policy"] == POLICY
            and payload["document_sha256"] == digest
            and payload["source_url"] == store.source_fields["offers_url"]
            and payload["observed_at"]
            == product.fetched_at.isoformat()
            == store.source_fields["pdf_observed_at"]
            and product.external_product_id == f"pdf:{digest}:p{ad['page']}:ad{ad['ad']}"
            and offer.external_id == product.external_product_id
            and product.name == ad["title"]
            and bool(ad["text_spans"])
            and bool(ad["price_spans"])
            and not ad["blockers"]
            and offer.price == Decimal(ad["purchase_price"])
            and product.package_quantity == (Decimal(ad["package_quantity"]) if ad['package_quantity'] else None)
            and product.package_unit == ad["package_unit"]
            and offer.member_only == ad["member_only"]
            and (offer.quantity or 1) == ad["required_packages"]
            and offer.max_quantity == ad["purchase_limit"]
            and str(offer.valid_from) == ad["valid_from"]
            and str(offer.valid_to) == ad["valid_to"]
            and (not product.source_fields.get('purchase_terms')
                 or offer.source_payload.get('purchase_terms') == product.source_fields['purchase_terms'])
        )
    except (KeyError, TypeError, ValueError, IndexError):
        return False


class XtraTextOfferConnector(CoopRowApprovedOfferConnector):
    """Same collector/OWN contract, isolated retained PDF transport."""

    parser_version = PARSER
    connector_version = "xtra-pdf-text-v1"

    def __init__(self, *, store, locator, offers):
        self.store, self.locator, self.offers = store, locator, offers
        self.row_acceptance = None

    def catalog_eligible(self, store):
        return (
            store.source_fields.get("offer_policy") == POLICY
            and store.source_fields.get("concept") == "X:-tra"
        )

    def parse_catalog(self, raw, references, store):
        from grocery_data.app.services.offer_rows import qualify_rows

        if len(raw.documents) != 1:
            raise ValueError("one source PDF required per bounded document import")
        self.extracted, self.layout_report = parse_pdf(raw.documents[0], store, references[0])
        result, self.row_acceptance = qualify_rows(
            self.extracted, store=store, observed_at=raw.documents[0].fetched_at
        )
        return result
