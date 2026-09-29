"""Manual isolated ICA area evaluation; refuses existing output/database paths."""
import argparse
import asyncio
import json
from pathlib import Path

from grocery_data.app.domain import GeographicArea
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.ica_area_offers import collect_area_offers
from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import create_database_engine, create_schema, create_session_factory


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", required=True)
    parser.add_argument("--area-mode", choices=("locality", "municipality"), default="locality")
    parser.add_argument("--municipality-code", help="Official SCB code; requires municipality mode")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--previous", type=Path)
    parser.add_argument("--skip-flyers", action="store_true")
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--row-approved-offers", action="store_true",
                        help="Explicit partial offers contract; preserves the full fetch's 95%% assessment")
    parser.add_argument("--extract-flyers", action="store_true")
    parser.add_argument("--visual-command-json", type=Path,
                        help="Operator-owned JSON argv for a public-page visual extractor; never shell text")
    parser.add_argument("--reviewed-transcriptions", type=Path)
    parser.add_argument("--approved-flyer-reviews", type=Path,
                        help="Evidence-bound reviewed new prices; normal row/OWN gates still apply")
    parser.add_argument("--previous-extraction", type=Path)
    parser.add_argument("--operation-database", type=Path, default=Path("var/grocery/grocery_data.sqlite"),
                        help="Existing database identity for the shared lock; never opened or written")
    parser.add_argument("--price-universe-root", type=Path, default=Path("var/price_universes"))
    args = parser.parse_args()
    from grocery_data.app.services.ica_flyer_pipeline import (
        extract_area,
        import_area_extractions,
        validated_new_batch,
    )

    approved = {}
    if args.approved_flyer_reviews:
        if not args.row_approved_offers:
            parser.error("reviewed flyer imports require the explicit row-approved contract")
        for entry in json.loads(args.approved_flyer_reviews.read_bytes()):
            account = entry["account"]
            approved.setdefault(account, []).append(validated_new_batch(entry["ad"], entry["review"], account=account))
    if args.output.exists():
        parser.error("output already exists; never overwrite retained evidence")
    database = args.output.with_suffix(".sqlite")
    if database.exists():
        parser.error("staging database already exists")
    engine = create_database_engine("sqlite:///" + database.resolve().as_posix())
    create_schema(engine)
    collector = GroceryCollector(create_session_factory(engine),
                                 FilesystemRawSnapshotStore(args.output.with_name(args.output.name + "-raw")))
    try:
        with RefreshRunLock(production_refresh_lock_path(args.operation_database, args.price_universe_root)):
            report = await collect_area_offers(
                GeographicArea(city=args.city, mode=args.area_mode, municipality_code=args.municipality_code), args.output, collector=collector,
                collect_flyers=not args.skip_flyers,
                inventory_only=args.inventory_only,
                row_approved_offers=args.row_approved_offers,
                approved_flyer_batches=approved,
                previous=json.loads(args.previous.read_bytes()) if args.previous else None)
            if args.extract_flyers:
                cache = json.loads(args.reviewed_transcriptions.read_bytes()) if args.reviewed_transcriptions else []
                previous = json.loads(args.previous_extraction.read_bytes())["observations"] if args.previous_extraction else []
                extraction = extract_area(report, args.output, database=database,
                    visual_command=json.loads(args.visual_command_json.read_bytes()) if args.visual_command_json else None,
                    reviewed_cache=cache.get("ads", []) if isinstance(cache, dict) else cache,
                    previous=previous)
                if args.row_approved_offers:
                    await import_area_extractions(report, extraction, args.output, database=database, collector=collector, previous=previous)
        print(json.dumps(report["coverage"]))
    finally:
        engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
