"""Municipal public flyers through the existing collector, OWN and lock."""
import argparse
import asyncio
import json
from pathlib import Path

from grocery_data.app.connectors.willys.flyer_client import FlyerClient
from grocery_data.app.connectors.willys.flyer_inventory import approved_flyer_stores, discover
from grocery_data.app.connectors.willys.flyer_offers import AutomaticWillysFlyerConnector
from grocery_data.app.domain import GeographicArea, RawBatch
from grocery_data.app.domain.municipality import municipality_name
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.coop_offer_job import write
from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import create_database_engine, create_schema, create_session_factory
from grocery_data.scripts.collect_citygross_municipality import _accepted_details


async def collect(inventory, store_ids, output, *, raw_by_store=None):
    approved = approved_flyer_stores(inventory)
    if not set(store_ids).issubset(approved):
        raise ValueError('collection escaped official flyer municipality')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write(output / 'inventory.json', inventory)
    report = {'municipality_code': inventory['area']['municipality_code'], 'stores': [],
        'production_activation': False, 'source_fetch_mode': 'replay' if raw_by_store is not None else 'fresh_network',
        'external_price_requests': 0}
    client = FlyerClient()
    try:
        for identity in sorted(store_ids):
            store = approved[identity]
            directory = output / identity
            directory.mkdir()
            database = directory / 'offers.sqlite'
            row = {'store_id': identity, 'name': store.name, 'municipality_status': 'inside',
                'source_url': store.source_fields['flyer_url'], 'source_format': 'public_iPaper_document_text',
                'coverage': 'offers_only', 'price_channel': 'physical_store_flyer', 'status': 'failed', 'own': 0,
                'database': database.relative_to(output).as_posix(), 'resolved_database': str(database.resolve())}
            engine = None
            try:
                raw = raw_by_store[identity] if raw_by_store is not None else await client.fetch(store)
                write(directory / 'source.json', raw.model_dump(mode='json'))
                connector = AutomaticWillysFlyerConnector(store=store, inventory=inventory, raw=raw)
                engine = create_database_engine('sqlite:///' + database.resolve().as_posix())
                create_schema(engine)
                collector = GroceryCollector(create_session_factory(engine), FilesystemRawSnapshotStore(directory / 'raw'))
                with RefreshRunLock(production_refresh_lock_path(database, directory / 'price-universes')):
                    result = await collector.collect_area(connector, GeographicArea.model_validate(inventory['area']),
                        scope_key=f"municipality:{inventory['area']['municipality_code']}:willys-flyer:{identity}:offer-rows")
                row.update(_accepted_details(database, result))
                row.update(status='success' if result.promoted else 'failed', qualification=connector.row_acceptance)
            except Exception as exc:  # noqa: BLE001 - optional store isolation
                row.update(reason=str(exc)[:200], error_type=type(exc).__name__)
            finally:
                if engine is not None:
                    engine.dispose()
            report['stores'].append(row)
            report['external_price_requests'] = client.requests
            write(directory / 'result.json', row)
            write(output / 'coverage.json', report)
    finally:
        await client.aclose()
    return report


async def run(args):
    area = GeographicArea(city=municipality_name(args.municipality_code), mode='municipality', municipality_code=args.municipality_code)
    inv = json.loads(args.inventory.read_bytes()) if args.inventory else await discover(area, args.output / 'inventory')
    if inv['area'] != area.model_dump(mode='json'):
        raise ValueError('inventory scope mismatch')
    stores = approved_flyer_stores(inv)
    raw = {i: RawBatch.model_validate_json((args.replay / f'live-{i}.json').read_bytes()) for i in stores} if args.replay else None
    result = await collect(inv, stores, args.output / 'collection', raw_by_store=raw)
    print(json.dumps([{k:r.get(k) for k in ('store_id','status','own','reason')} for r in result['stores']]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--municipality-code', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--replay', type=Path)
    asyncio.run(run(parser.parse_args()))


if __name__ == '__main__':
    main()
