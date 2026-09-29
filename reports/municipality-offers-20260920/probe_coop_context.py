"""Audit only: retain public date text already read by existing browser transport."""
import asyncio,json,re
from pathlib import Path
from datetime import datetime,UTC
from grocery_data.app.domain import SourceStore
from grocery_data.app.connectors.coop.browser import CoopBrowserOffersTransport
ROOT=Path(__file__).parent
class ContextAudit(CoopBrowserOffersTransport):
    def _declared_offer_total(self,visible):
        lines=visible.splitlines();self.context=[]
        for i,line in enumerate(lines):
            if re.search(r"gäller|vecka|\d{1,2}/\d{1,2}|erbjudande",line,re.I):
                self.context.append({"line":i,"text":" ".join(lines[max(0,i-1):i+3])[:400]})
        return super()._declared_offer_total(visible)
async def main():
    audit=json.loads((ROOT/"coop-audit.json").read_bytes())
    for row in audit["stores"]:
        if row["offer_check"]!="live_bounded":continue
        store=SourceStore(**row["store"]);transport=ContextAudit()
        raw=await transport.fetch(store)
        payload={"store_id":store.external_id,"source_url":raw.url,"observed_at":raw.fetched_at.isoformat(),"context":transport.context,"offer_payload_sha256":raw.payload_hash,"purpose":"diagnose discarded public period text, not ingestion or approval"}
        (ROOT/("coop-"+store.external_id+"-date-context.json")).write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
        (ROOT/("coop-"+store.external_id+"-context-cards.json")).write_bytes(raw.payload)
        print(store.external_id,payload["context"][:12],flush=True)
asyncio.run(main())
