import asyncio,json
from pathlib import Path
from grocery_data.app.domain import SourceStore,RawBatch,Chain
from grocery_data.app.connectors.willys import WillysConnector
from grocery_data.app.connectors.willys.client import WillysClient
from grocery_data.app.connectors.hemkop import HemkopConnector
from grocery_data.app.connectors.hemkop.client import HemkopClient
from grocery_data.app.connectors.http import RetryPolicy
ROOT=Path(__file__).parent
async def main():
 for chain,codes in [("willys",["101291418_ST","101804196_ST","101804191_ST"]),("hemkop",["101357777_ST","101846251_ST","101551978_ST"])]:
  audit=json.loads((ROOT/(chain+"-audit.json")).read_bytes())
  for row in audit["stores"]:
   if row["offer_check"]!="live_bounded":continue
   store=SourceStore(**row["store"])
   if chain=="willys": con=WillysConnector(client=WillysClient(retry_policy=RetryPolicy(attempts=1)))
   else: con=HemkopConnector(client=HemkopClient(allow_full_crawl=False,retry_policy=RetryPolicy(attempts=1)))
   docs=[]
   try:
    await con.client._activate_store(store.external_id,docs)
    for code in codes: docs.append(await con.client.fetch_product_detail(store,code))
    batch=RawBatch(chain=Chain(chain),documents=tuple(docs));stem=chain+"-"+store.external_id+"-details"
    (ROOT/(stem+".json")).write_text(batch.model_dump_json(indent=2),encoding="utf-8")
    parsed=con.parse_catalog(batch,[stem+".json#"+str(i) for i in range(len(docs))],store)
    (ROOT/(stem+"-parsed.json")).write_text(parsed.model_dump_json(indent=2),encoding="utf-8")
    print(chain,store.external_id,[(p.name,[(o.price,o.quantity,o.valid_to) for o in p.offers]) for p in parsed.products],flush=True)
   finally:await con.aclose()
asyncio.run(main())
