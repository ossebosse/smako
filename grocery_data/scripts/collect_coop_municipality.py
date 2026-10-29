"""Explicit isolated municipal pipeline for Coop/Stora Coop/X:-tra. No activation."""
import argparse
import asyncio
import copy
import json
from pathlib import Path

from grocery_data.app.connectors.coop.municipality_inventory import discover
from grocery_data.app.connectors.coop.xtra_publications import fetch_publications
from grocery_data.app.domain import GeographicArea
from grocery_data.app.domain.municipality import municipality_name
from grocery_data.app.services.area_membership import approved_municipal_stores
from grocery_data.app.services.coop_municipal_refresh import update_selection
from grocery_data.scripts.collect_coop_physical_offers import collect


async def project_structured(inventory, database):
    import httpx
    from app.providers.coop_municipality_offers import CoopMunicipalityOfferProvider
    from app.providers.own import OwnGroceryPriceProvider
    from fastapi import FastAPI

    from grocery_data.app.api import catalog_router
    from grocery_data.app.storage import create_database_engine, create_session_factory

    class EmptyBase:
        async def find_stores(self,postal):return []
        def report(self):return {}
    engine=create_database_engine("sqlite:///"+database.resolve().as_posix())
    try:
        app=FastAPI();app.state.session_factory=create_session_factory(engine);app.include_router(catalog_router)
        async with httpx.AsyncClient(base_url="http://isolated",transport=httpx.ASGITransport(app=app)) as client:
            own=OwnGroceryPriceProvider("http://isolated",client=client,include_offers_only=True,include_conditional_offer_products=True)
            provider=CoopMunicipalityOfferProvider(EmptyBase(),own,database=database,inventory=inventory)
            await provider.find_stores("")  # Explicit municipality IDs, no invented user postcode.
            return [p for values in provider.products.values() for p in values],provider.diagnostics
    finally:engine.dispose()


async def collect_xtra(row, inventory, output):
    from app.models.product import Product

    from grocery_data.scripts.import_xtra_pdf_text import run as import_pdf

    publications=await fetch_publications(row,output)
    if (publications.get("publication_status") == "confirmed_no_current_publication"
            and publications["editions"] == [] and publications.get("discovered_links") == []
            and publications.get("store_page_sha256") and publications.get("store_page_observed_at")):
        publications.update(status="confirmed_no_qualified_rows",own=0,quarantine=0,
                            price_universe=0,windows=[],
                            observed_at=publications["store_page_observed_at"],
                            source_version=[publications["store_page_sha256"]])
        (output/"result.json").write_text(json.dumps(publications,ensure_ascii=False,indent=2),encoding="utf8")
        return publications,[]
    products=[];windows=[];own=0;quarantine=0;observations=[];seen={}
    for edition in publications["editions"]:
        if edition["status"]!="text_ready":continue
        if edition["sha256"] in seen:
            edition.update(import_status="already_covered_exact_document",covered_by=seen[edition["sha256"]],own=0,price_universe=0)
            continue
        seen[edition["sha256"]]=edition["directory"]
        folder=Path(edition["directory"])
        bound=copy.deepcopy(inventory)
        target=next(r for r in bound["stores"] if r["store"]["external_id"]==row["store"]["external_id"])
        target["store"]["source_fields"]["offers_url"]=edition["source_url"]
        # Only the public store binding and freshly observed source link change.
        inventory_path=folder/"inventory.json";inventory_path.write_text(json.dumps(bound,ensure_ascii=False),encoding="utf8")
        try:
            report=await import_pdf(inventory_path,folder/"result.json",folder/"source.pdf",folder/"import")
            edition["import_status"]="blocked_layout_or_shared_evidence" if report["qualification"]["shared_blockers"] else "partial_text_candidate"
            edition["blockers"]=report["qualification"]["shared_blockers"]
            edition["own"]=report["metrics"]["products_parsed"] if report["partial_promoted"] else 0
            edition["price_universe"]=report["price_universe_count"]
            edition["parsed_ads"]=sum(len(p["ads"]) for p in report["pages"])
            edition["unclassified_ads"]=None
            edition["layout_gaps"]=[{"page":p["page"],"unclassified_price_spans":p["unclassified_price_spans"],"unassigned_condition_spans":p["unassigned_condition_spans"]} for p in report["pages"] if not p["ads"] or p["unclassified_price_spans"] or p["unassigned_condition_spans"]]
            if not edition["parsed_ads"] and not edition["blockers"]:
                edition["import_status"]="unsupported_text_layout"
            own+=edition["own"];quarantine+=report["metrics"]["products_quarantined"]
            artifact=json.loads((folder/"import/price-universe.json").read_bytes())
            products.extend(Product.model_validate(p) for p in artifact["products"])
            if not edition["blockers"]:
                windows.extend({"valid_from":a["valid_from"],"valid_to":a["valid_to"]} for page in report["pages"] for a in page["ads"])
                observations.append(edition["observed_at"])
        except Exception as exc:  # noqa: BLE001 - keep every failed edition/store
            edition.update(import_status="blocked_import",error_type=type(exc).__name__,reason=str(exc)[:300])
    successful=bool(publications["editions"]) and all(e.get("import_status") in {"partial_text_candidate","already_covered_exact_document"} for e in publications["editions"])
    publications.update(status="partial_text_candidate" if successful else "blocked_or_incomplete_publications",own=own,
                        quarantine=quarantine,price_universe=len(products),windows=windows,
                        observed_at=min(observations) if observations else None,
                        source_version=[e.get("sha256") for e in publications["editions"]])
    (output/"result.json").write_text(json.dumps(publications,ensure_ascii=False,indent=2),encoding="utf8")
    return publications,products


async def run(code, output, *, inventory_path=None, previous_path=None, due_only=False, structured_input=None):
    from app.services.price_universe import PriceUniverseBuilder, PriceUniverseKey

    if output.exists():raise ValueError("refusing to overwrite prior evidence")
    output.mkdir(parents=True)
    area=GeographicArea(city=municipality_name(code),mode="municipality",municipality_code=code)
    inventory=json.loads(inventory_path.read_bytes()) if inventory_path else await discover(area,output/"inventory")
    if inventory["area"]["municipality_code"]!=code:raise ValueError("inventory belongs to another municipality")
    approved=approved_municipal_stores(inventory,concepts=("Coop","Stora Coop","X:-tra"))
    previous=json.loads(previous_path.read_bytes()) if previous_path else None
    initial=update_selection(inventory,previous=previous)
    chosen=set(initial["due_store_ids"]) if due_only else set(approved)
    if not chosen:
        for row in inventory["stores"]:
            identity=row["store"]["external_id"]
            row["pipeline"]={"status":"not_due" if identity in approved else "not_selected",
                             "own":None,"price_universe":None}
        report={"inventory":inventory,"municipality_code":code,"production_activation":False,
                "candidate_status":"not_built_no_due_work","price_universe_id":None,
                "price_universe_count":None,"source_fetch_mode":"no_external_price_calls"}
        (output/"update-selection.json").write_text(json.dumps(initial,ensure_ascii=False,indent=2),encoding="utf8")
        (output/"coverage.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
        return report
    selected={i for i in chosen if approved[i].source_fields["concept"] in {"Coop","Stora Coop"}}
    scoped={**inventory,"selected_store_ids":sorted(selected)}
    collection_root=structured_input or output/"collection"
    if structured_input:
        collection=json.loads((structured_input/"coverage.json").read_bytes())
        if {r["store_id"] for r in collection["stores"]} != selected:
            raise ValueError("retained structured collection does not match municipal selection")
    else:
        collection=await collect(scoped,selected,collection_root) if selected else {"stores":[]}
    products,projection=await project_structured(scoped,collection_root/"own.sqlite") if selected else ([],{})
    outcomes={}
    for row in collection["stores"]:
        identity=row["store_id"];row["price_universe"]=projection.get(identity,{}).get("accepted",0)
        row["projection"]=projection.get(identity,{})
        if row["status"]=="partial_candidate" and row["projection"].get("status")!="success":
            row["status"]="blocked_projection"
        windows=[];path=collection_root/"sources"/(identity+"-extracted.json")
        if path.exists():
            parsed=json.loads(path.read_bytes())
            windows=[{k:o.get(k) for k in ["valid_from","valid_to"]} for p in parsed["products"] for o in p["offers"]]
        outcomes[identity]={**row,"windows":windows,"source_version":row.get("source_hash")}
    for row in inventory["stores"]:
        identity=row["store"]["external_id"]
        if identity not in chosen or identity not in approved:continue
        if row["store"]["source_fields"]["concept"]=="X:-tra":
            try:
                outcome,extra=await collect_xtra(row,inventory,output/("xtra-"+identity));products.extend(extra)
                outcomes[identity]=outcome
            except Exception as exc:  # noqa: BLE001 - never lose failed store from coverage
                outcomes[identity]={"status":"failed_publication_discovery","error_type":type(exc).__name__,"reason":str(exc)[:300],"own":0,"price_universe":0}
    key=PriceUniverseKey.create(city=area.city,snapshot_ids=sorted({p.source_provenance.source_snapshot_id for p in products}),
        source_strategy_version="municipal-coop-candidate-v1:"+area.area_key,
        normalizer_version="product-normalizer-v3-recipe-taxonomy",taxonomy_version="existing-taxonomy-v1")
    universe=PriceUniverseBuilder().build(key,products)
    (output/"price-universe.json").write_text(universe.model_dump_json(indent=2),encoding="utf8")
    selection=update_selection(inventory,outcomes,previous=previous)
    (output/"update-selection.json").write_text(json.dumps(selection,ensure_ascii=False,indent=2),encoding="utf8")
    for row in inventory["stores"]:
        identity=row["store"]["external_id"]
        row["pipeline"]=outcomes.get(identity,{"status":"not_due" if identity in approved and identity not in chosen else "not_selected","own":None,"price_universe":None})
    report={"inventory":inventory,"collection":collection,"municipality_code":code,
            "inventory_mode":"retained_observation" if inventory_path else "fresh_network",
            "source_fetch_mode":"retained_structured_plus_fresh_xtra" if structured_input else "fresh_network_for_selected_stores","production_activation":False,
            "price_universe_id":universe.universe_id,"price_universe_count":len(universe.products)}
    (output/"coverage.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf8")
    print(json.dumps({"municipality":code,"selected":sorted(chosen),"pu":len(universe.products),
                      "outcomes":{k:{x:v.get(x) for x in ['status','own','price_universe']} for k,v in outcomes.items()}},ensure_ascii=False))
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--municipality-code",required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--inventory",type=Path)
    parser.add_argument("--previous-state",type=Path)
    parser.add_argument("--structured-input",type=Path,help="Revalidate retained isolated structured collection; never a new observation")
    parser.add_argument("--due-only",action="store_true")
    args=parser.parse_args()
    asyncio.run(run(args.municipality_code,args.output,inventory_path=args.inventory,previous_path=args.previous_state,due_only=args.due_only,structured_input=args.structured_input))
