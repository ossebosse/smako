"""Hemköp municipal selection in the existing locked refresh/OWN lifecycle."""
import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy.engine import make_url

from grocery_data.app.services.area_membership import approved_municipal_stores, collection_area
from grocery_data.app.services.coop_offer_job import read, write


def configuration(city=None, *, environment=None, persist=False):
    env = os.environ if environment is None else environment
    city = city or env.get('REFRESH_CITY', 'Lund')
    area = collection_area(city, environment=env, persist=persist)
    database = Path(make_url(env.get('GROCERY_DATABASE_URL', 'sqlite:///var/grocery/grocery_data.sqlite')).database)
    root = Path(env.get('HEMKOP_MUNICIPAL_ROOT', str(database.parent / 'hemkop-municipal')))
    return area, root / str(area.municipality_code), env.get('HEMKOP_MUNICIPAL_OFFERS_ENABLED', 'false').casefold() == 'true' and area.mode == 'municipality'


def source_plan(*, city=None, environment=None, now=None):
    now = now or datetime.now(UTC)
    area, root, enabled = configuration(city, environment=environment)
    state = read(root / 'source-state.json') if enabled else {}
    schedules = state.get('store_schedule', {})
    for schedule in schedules.values():
        if schedule.get('last_success_at') and not schedule.get('failed_attempts'):
            schedule['next_fetch_at'] = min(datetime.fromisoformat(schedule['next_fetch_at']),
                datetime.fromisoformat(schedule['last_success_at']) + timedelta(hours=35)).isoformat()
    due = [k for k, v in schedules.items() if datetime.fromisoformat(v['next_fetch_at']) <= now]
    inventory_due = enabled and (not state or datetime.fromisoformat(state['next_inventory_at']) <= now)
    fingerprint = hashlib.sha256(json.dumps({'area': area.model_dump(mode='json'), 'enabled': enabled,
        'database': state.get('database'), 'approved': state.get('approved_store_ids')}, sort_keys=True).encode()).hexdigest()
    return {'enabled': enabled, 'work_due': bool(enabled and (inventory_due or due)),
        'inventory_due': inventory_due, 'due_store_ids': due, 'store_schedule': schedules,
        'fingerprint': fingerprint, 'external_price_requests': 0}


def source_inputs(*, city):
    try:
        area, root, enabled = configuration(city)
        state = read(root / 'source-state.json') if enabled else {}
        if not state or state['inventory']['area'] != area.model_dump(mode='json'):
            return {}
        database = Path(state['database']).resolve(strict=True)
        if not database.is_relative_to(root.resolve()):
            raise ValueError('Hemkop source outside owned root')
        selected = approved_municipal_stores(state['inventory'])
        if any(s.chain.value != 'hemkop' for s in selected.values()):
            raise ValueError('Hemkop inventory contains another chain')
        ids = set(state['approved_store_ids']) & selected.keys()
        return {'hemkop_offer_database': database,
            'hemkop_municipal_stores': {k: selected[k] for k in ids}}
    except (ValueError, KeyError, OSError, TypeError):
        return {}


def catalog_stores(city, *, environment=None):
    """Official municipal selection for catalog discovery, independent of offers."""
    from grocery_data.app.services.municipal_rollout import scope_for_city

    if scope_for_city(city, environment) is None:
        return None
    area, root, enabled = configuration(city, environment=environment)
    if not enabled:
        return {}
    state = read(root / 'source-state.json')
    if not state or state.get('inventory', {}).get('area') != area.model_dump(mode='json'):
        raise ValueError('verified Hemkop municipal inventory required for catalog build')
    return {identity: store for identity, store in approved_municipal_stores(state['inventory']).items()
            if store.online_shopping is True}


def persist_official_inventory(inventory, database):
    """Reuse exact physical/context registry; capability is never price approval."""
    from sqlalchemy.orm import Session

    from grocery_data.app.domain import PhysicalStore
    from grocery_data.app.services.official_store_discovery import (
        _source_context_capability,
        stable_physical_store_id,
    )
    from grocery_data.app.services.store_coverage import ExactStoreIdentityMatcher
    from grocery_data.app.storage import (
        PhysicalStoreRepository,
        StoreContextLinkRepository,
        create_database_engine,
    )

    engine = create_database_engine('sqlite:///' + database.resolve().as_posix())
    try:
        with Session(engine) as session, session.begin():
            for store in approved_municipal_stores(inventory).values():
                if store.chain.value != 'hemkop':
                    raise ValueError('Hemkop municipal registry chain mismatch')
                source = store.source_fields['coordinate_source']
                observed = datetime.fromisoformat(source['observed_at'])
                physical = PhysicalStore(id=stable_physical_store_id(store.chain, store.external_id),
                    chain=store.chain, external_store_id=store.external_id, name=store.name,
                    address=store.address, postal_code=store.postal_code, city=store.city,
                    latitude=store.latitude, longitude=store.longitude, official_source=source['url'],
                    discovered_at=observed, last_seen_at=observed)
                PhysicalStoreRepository(session).upsert(physical, seen_at=observed)
                context = _source_context_capability(store, observed_at=observed)
                if context is not None:
                    for match in ExactStoreIdentityMatcher.physical_to_context(physical, [context]):
                        links = StoreContextLinkRepository(session)
                        # Keep prior approved catalog snapshot and lineage intact.
                        current = links.get(physical.id, source_provider='own', grocery_context_id=context.grocery_context_id)
                        if current is None:
                            links.upsert(match.as_link(physical.id, verified_at=observed))
    finally:
        engine.dispose()


async def run_source_job(*, city=None, environment=None, now=None):
    """Caller owns normal refresh lock; no catalog traversal or mandatory-policy edit."""
    from grocery_data.app.connectors.hemkop import HemkopConnector
    from grocery_data.app.connectors.hemkop.client import HemkopAccessChallenge, HemkopRateLimitStop
    from grocery_data.app.connectors.hemkop.physical_offers import RetainedPhysicalOffers, fetch
    from grocery_data.app.connectors.willys.municipality_inventory import build_inventory
    from grocery_data.app.domain import RawBatch
    from grocery_data.app.services.campaign_refresh_policy import campaign_schedule
    from grocery_data.app.services.collector import GroceryCollector
    from grocery_data.app.services.municipality_geometry import fetch_boundary, validate_boundary
    from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
    from grocery_data.app.storage import (
        create_database_engine,
        create_schema,
        create_session_factory,
    )

    now = now or datetime.now(UTC)
    area, root, enabled = configuration(city, environment=environment, persist=True)
    if not enabled:
        return {'status': 'disabled', 'external_price_requests': 0}
    plan = source_plan(city=city, environment=environment, now=now)
    prior = read(root / 'source-state.json')
    if not plan['work_due']:
        if prior.get('store_schedule') != plan['store_schedule']:
            prior['store_schedule'] = plan['store_schedule']
            write(root / 'source-state.json', prior)
        env = os.environ if environment is None else environment
        database = Path(make_url(env.get('GROCERY_DATABASE_URL', 'sqlite:///var/grocery/grocery_data.sqlite')).database)
        persist_official_inventory(prior['inventory'], database)
        return {**prior, 'status': 'not_due', 'external_price_requests': 0}
    attempt = root / 'attempts' / (now.strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8])
    attempt.mkdir(parents=True)
    connector = HemkopConnector.for_bounded_discovery()
    engine = None
    try:
        if plan['inventory_due']:
            boundary = read(root / 'boundary.json')
            if not boundary:
                boundary = await fetch_boundary(area.municipality_code)
                write(root / 'boundary.json', boundary)
            validate_boundary(boundary)
            locator = await connector.fetch_stores(area)
            write(attempt / 'locator.json', locator.model_dump(mode='json'))
            inventory = build_inventory(area, locator, [str(attempt / 'locator.json')], boundary, parser=connector.parser)
            for row in inventory['stores']:
                row['sources'] = {'online_catalog': row['store']['online_shopping'] is True,
                    'physical_structured_offers': True, 'linked_flyer': row['store']['source_fields'].get('flyer_url')}
            inventory['selected_store_ids'] = sorted(approved_municipal_stores(inventory))
        else:
            inventory = prior['inventory']
            locator = RawBatch.model_validate(read(Path(prior['locator'])))
        selected = approved_municipal_stores(inventory)
        env = os.environ if environment is None else environment
        main_database = Path(make_url(env.get('GROCERY_DATABASE_URL', 'sqlite:///var/grocery/grocery_data.sqlite')).database)
        persist_official_inventory(inventory, main_database)
        database = attempt / 'offers.sqlite'
        if prior.get('database'):
            old = Path(prior['database']).resolve(strict=True)
            if not old.is_relative_to(root.resolve()):
                raise ValueError('Hemkop prior database outside owned root')
            with sqlite3.connect(old.as_uri() + '?mode=ro', uri=True) as src, sqlite3.connect(database) as dst:
                src.backup(dst)
            from grocery_data.app.services.snapshot_retention import compact_candidate_copy
            compact_candidate_copy(database, attempt / 'raw', now=now)
        engine = create_database_engine('sqlite:///' + database.resolve().as_posix())
        create_schema(engine)
        collector = GroceryCollector(create_session_factory(engine), FilesystemRawSnapshotStore(attempt / 'raw'))
        schedules = {k: v for k, v in prior.get('store_schedule', {}).items() if k in selected}
        approved = set(prior.get('approved_store_ids', [])) & selected.keys()
        outcomes = dict(prior.get('outcomes', {}))
        access_stop = None
        for identity, store in selected.items():
            if identity in schedules and identity not in plan['due_store_ids']:
                continue
            if access_stop:
                failures = schedules.get(identity, {}).get('failed_attempts', 0) + 1
                schedules[identity] = {**schedules.get(identity, {}),
                    **campaign_schedule([], now=now, failed_attempts=failures), 'failed_attempts': failures}
                outcomes[identity] = {'status': 'not_requested_after_access_stop', 'reason': access_stop,
                    'own_rows': None, 'external_price_requests': 0}
                continue
            try:
                batch = await fetch(connector.client, store)
                write(attempt / (identity + '-offers.json'), batch.model_dump(mode='json'))
                retained = RetainedPhysicalOffers(connector, store, locator, batch)
                result = await collector.collect_area(retained, area, auto_promote=True,
                    scope_key=f'{area.city.casefold()}:hemkop:{identity}:offer-rows')
                evidence = retained.row_acceptance
                windows = [{'valid_from': p.get('startDate'), 'valid_to': p.get('endDate')}
                    for d in batch.documents for r in d.json_payload().get('results') or [] for p in r.get('potentialPromotions', [])]
                windows = [{k: datetime.strptime(v, '%d/%m-%Y').replace(tzinfo=UTC).date().isoformat() if v else None
                    for k, v in w.items()} for w in windows]
                observed = min(d.fetched_at for d in batch.documents).isoformat()
                outcomes[identity] = {'status': 'approved' if result.promoted else 'rows_quarantined',
                    'snapshot_id': result.snapshot_id, 'source': f'https://www.hemkop.se/erbjudanden/{identity}',
                    'api': batch.documents[0].url, 'query': batch.documents[0].query,
                    'observed_at': observed, 'acceptance': evidence, 'windows': windows,
                    'own_rows': result.metrics.products_parsed if result.promoted else 0}
                if result.promoted:
                    approved.add(identity)
                else:
                    approved.discard(identity)
                schedules[identity] = {**campaign_schedule(windows, now=now), 'failed_attempts': 0,
                    'last_success_at': observed, 'campaign_windows': windows}
                schedules[identity]['next_fetch_at'] = min(
                    datetime.fromisoformat(schedules[identity]['next_fetch_at']),
                    datetime.fromisoformat(observed) + timedelta(hours=35)).isoformat()
            except Exception as exc:  # noqa: BLE001 - independent optional source keeps LKG
                if isinstance(exc, (HemkopAccessChallenge, HemkopRateLimitStop)):
                    access_stop = type(exc).__name__
                    write(attempt / (identity + '-access-stop.json'), exc.raw.model_dump(mode='json'))
                failures = schedules.get(identity, {}).get('failed_attempts', 0) + 1
                schedules[identity] = {**schedules.get(identity, {}),
                    **campaign_schedule([], now=now, failed_attempts=failures), 'failed_attempts': failures}
                outcomes[identity] = {'status': 'source_failed_lkg_retained', 'error_type': type(exc).__name__,
                    'reason': str(exc)[:250], 'own_rows': None}
        current = {'status': 'municipal_optional_source', 'inventory': inventory,
            'database': str(database), 'locator': str(attempt / 'locator.json') if plan['inventory_due'] else prior['locator'],
            'approved_store_ids': sorted(approved), 'store_schedule': schedules, 'outcomes': outcomes,
            'next_inventory_at': (now + timedelta(hours=72)).isoformat() if plan['inventory_due'] else prior['next_inventory_at'],
            'mandatory_contexts_changed': False}
        write(root / 'source-state.json', current)
        return current
    finally:
        if engine is not None:
            engine.dispose()
        await connector.aclose()
