"""Final code verification from unchanged official responses; zero network."""
import asyncio,json
from pathlib import Path
from datetime import datetime
import httpx
from grocery_data.app.domain import GeographicArea,RawFetch,RawBatch,Chain
from grocery_data.app.connectors.ica.parser import IcaParser
from grocery_data.app.services.ica_area_offers import collect_area_offers
ROOT=Path(__file__).parent
class Retained:
    parser=IcaParser()
    def __init__(self,code):
        self.root=ROOT/("ica-"+code)
        self.report=json.loads((self.root/"coverage.json").read_bytes())
    async def fetch_physical_stores(self,area):
        if area.mode=="municipality":
            name="locator-0.json";url=self.report["stores"][0]["discovery_sources"][0];observed=self.report["stores"][0]["discovered_at"]
        else:
            entries=json.loads((self.root/"coverage-enriched.json").read_bytes())["municipality_address_enrichment"]["queries"]
            index=next(i for i,x in enumerate(entries) if x["locality"]==area.city)
            entry=entries[index];name=f"municipality-address-{index}-0.json";url=entry["source_urls"][0];observed=entry["observed_at"]
        doc=RawFetch(chain=Chain.ICA,kind="stores_page",method="GET",url=url,fetched_at=datetime.fromisoformat(observed),http_status=200,content_type="application/json",connector_version="ica-v2",payload=(self.root/name).read_bytes())
        return RawBatch(chain=Chain.ICA,documents=(doc,))
    async def aclose(self):pass
async def deny(*args,**kwargs):raise AssertionError("Network forbidden in replay")
async def main():
    httpx.AsyncClient.send=deny
    areas=[GeographicArea(city=city,mode="municipality",municipality_code=code) for city,code in [("Lund","1281"),("Malmö","1280")]]
    references=[]
    for area in areas:
        con=Retained(area.municipality_code);batch=await con.fetch_physical_stores(area)
        references.extend(con.parser.parse_physical_stores(batch,[str(con.root/"locator-0.json")],area,include_outside=True))
    for area in areas:
        target=ROOT/("verified-"+area.municipality_code)
        r=await collect_area_offers(area,target,connector=Retained(area.municipality_code),inventory_only=True,collect_flyers=False,discover_flyers=False,municipality_reference_stores=references)
        (target/"execution.json").write_text(json.dumps({"mode":"offline final-code replay of live 2026-09-20 responses","network_blocked":True,"external_requests":0,"source_observations_preserved":True},indent=2),encoding="utf-8")
        print(area.city,r["area_counts"])
asyncio.run(main())
