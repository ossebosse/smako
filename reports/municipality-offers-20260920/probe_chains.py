"""Bounded manual audit. Existing clients only, no collector/promotion/config writes."""
import asyncio
from datetime import UTC, datetime
import json
from pathlib import Path
from grocery_data.app.domain import GeographicArea
from grocery_data.app.connectors.http import RetryPolicy
from grocery_data.app.connectors.willys import WillysConnector
from grocery_data.app.connectors.willys.client import WillysClient
from grocery_data.app.connectors.hemkop import HemkopConnector
from grocery_data.app.connectors.hemkop.client import HemkopClient
from grocery_data.app.connectors.citygross import CityGrossConnector
from grocery_data.app.connectors.citygross.client import CityGrossClient
from grocery_data.app.connectors.coop import CoopConnector
from grocery_data.app.connectors.lidl import LidlConnector
from grocery_data.app.connectors.lidl.client import LidlClient
from grocery_data.app.services.area_membership import assess_area

ROOT = Path(__file__).parent

def save_batch(batch, stem):
    data = batch.model_dump(mode="json")
    (ROOT / (stem + ".json")).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")

def save(value, stem):
    (ROOT / (stem + ".json")).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8")

async def run():
    results=[]
    for chain in ["willys", "hemkop", "citygross", "lidl", "coop"]:
        if (ROOT/(chain+"-audit.json")).exists():
            continue
        if chain == "willys":
            con=WillysConnector(client=WillysClient(page_size=30,max_categories=1,max_pages_per_category=1,retry_policy=RetryPolicy(attempts=1)))
        elif chain == "hemkop":
            con=HemkopConnector(client=HemkopClient(page_size=30,max_categories=1,max_pages_per_category=1,allow_full_crawl=False,retry_policy=RetryPolicy(attempts=1)))
        elif chain == "citygross":
            con=CityGrossConnector(client=CityGrossClient(page_size=30,max_pages=1,allow_full_crawl=False,retry_policy=RetryPolicy(attempts=1)))
        elif chain == "lidl":
            con=LidlConnector(client=LidlClient(page_size=30,max_pages=1,retry_policy=RetryPolicy(attempts=1)))
        else:
            con=CoopConnector()
        report={"chain":chain,"started":datetime.now(UTC).isoformat(),"runtime":"local Windows Python 3.12", "municipality_inventory_complete":False,"stores":[],"errors":[]}
        try:
            for city,code in [("Lund","1281"),("Malmö","1280")]:
                area=GeographicArea(city=city)
                batch=await (con.fetch_physical_stores(area) if chain=="coop" else con.fetch_stores(area))
                stem=chain+"-"+code+"-locator"; save_batch(batch,stem)
                refs=[stem+".json#"+str(i) for i in range(len(batch.documents))]
                stores=(con.parse_physical_stores(batch,refs,area) if chain=="coop" else con.parse_stores(batch,refs,area))
                for store in stores:
                    row={"store":store.model_dump(mode="json"),"discovery_area":city,"municipality":assess_area(store,GeographicArea(city=city,mode="municipality",municipality_code=code)),"offer_check":"not_sampled", "own":"not_verified", "active_pu":"not_verified", "recipe_purchase":"not_verified"}
                    report["stores"].append(row)
                candidates=[s for s in stores if con.catalog_eligible(s)]
                # Existing blocked Karhögstorg traversal is not retried.
                if chain=="hemkop" and city=="Lund": candidates=[s for s in candidates if s.external_id!="4123"]
                if chain=="lidl" and city!="Lund": candidates=[] # one regional price feed, not one per shop
                if candidates:
                    store=candidates[0]
                    row=next(r for r in report["stores"] if r["store"]["external_id"]==store.external_id)
                    try:
                        offers=await con.fetch_catalog(store)
                        ostem=chain+"-"+store.external_id+"-sample";save_batch(offers,ostem)
                        parsed=con.parse_catalog(offers,[ostem+".json#"+str(i) for i in range(len(offers.documents))],store)
                        save(parsed.model_dump(mode="json"),ostem+"-parsed")
                        row.update(offer_check="live_bounded",parsed_file=ostem+"-parsed.json",raw_file=ostem+".json",observed_at=max(d.fetched_at for d in offers.documents).isoformat(),products=len(parsed.products),failures=len(parsed.failures),offers=sum(len(p.offers) for p in parsed.products))
                    except Exception as exc:
                        if hasattr(exc,"partial_batch"): save_batch(exc.partial_batch,chain+"-"+store.external_id+"-failed")
                        row.update(offer_check="failed",error=type(exc).__name__,detail=str(exc)[:350])
                        report["errors"].append(type(exc).__name__)
                        # Stop this chain on challenge/access failure; never retry another context.
                        if 'Access' in type(exc).__name__ or 'challenge' in str(exc).lower() or '403' in str(exc): break
                # National locator can be replayed offline for the other city, but this bounded
                # implementation keeps two explicit city checks for independent metadata.
        except Exception as exc:
            if hasattr(exc,"partial_batch"): save_batch(exc.partial_batch,chain+"-discovery-failed")
            report["errors"].append({"type":type(exc).__name__,"detail":str(exc)[:350]})
        finally:
            await con.aclose()
        report["finished"]=datetime.now(UTC).isoformat(); save(report,chain+"-audit"); results.append(report)
        print(chain,len(report["stores"]),report["errors"],flush=True)
    save(results,"probe-results")

if __name__=="__main__": asyncio.run(run())
