"""Optional candidate job in the existing managed-refresh operation lock.

No production source activation. Every attempt has immutable raw/SQLite output;
a failed attempt cannot replace the previous reviewable candidate pointer.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from grocery_data.app.domain import GeographicArea
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.durable_files import atomic_write_bytes
from grocery_data.app.services.ica_area_offers import collect_area_offers, offer_store_proposal
from grocery_data.app.services.ica_flyer_pipeline import extract_area, import_area_extractions
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import create_database_engine, create_schema, create_session_factory


def source_location(city, root, *, environment=None, persist=False):
    from grocery_data.app.services.area_membership import collection_area

    area = collection_area(city, environment=environment, persist=persist)
    key = area.municipality_code if area.mode == 'municipality' else ''.join(c if c.isalnum() else '-' for c in city.casefold())
    return area, root / key


def municipal_stores(coverage):
    from grocery_data.app.domain import SourceStore
    from grocery_data.app.services.area_membership import assess_area

    area = GeographicArea.model_validate(coverage['area'])
    if area.mode != 'municipality':
        raise ValueError('municipal evidence required')
    result = {}
    for row in coverage['stores']:
        store = SourceStore.model_validate(row['store'])
        if row.get('inventory_status') == 'not_seen_in_current_inventory':
            continue
        if store.chain.value != 'ica' or store.external_id != row['ica_account_id']:
            raise ValueError('ICA inventory identity conflict')
        if assess_area(store, area)['status'] == 'inside':
            if store.external_id in result:
                raise ValueError('duplicate municipal ICA identity')
            result[store.external_id] = store
    return result


async def run_structured_offer_job(*, city: str, root: Path, now=None, force=False,
                                   collect=collect_area_offers) -> dict:
    """Production opt-in, structured sources only; caller owns refresh lock.

    Reuses the existing OWN schema/collector. Immutable attempt databases retain
    independent store LKGs; the explicit source pointer is consumed by the normal
    PriceUniverse builder. It does not activate a PriceUniverse by itself.
    """
    from grocery_data.app.services.campaign_refresh_policy import (
        campaign_schedule,
        scheduled_source_times,
    )
    now = now or datetime.now(UTC)
    area, base = source_location(city, root, persist=True)
    base.mkdir(parents=True, exist_ok=True)
    pointer = base / 'structured-source.json'
    previous = json.loads(pointer.read_bytes()) if pointer.exists() else {}
    schedule = previous.get('store_schedule', {})
    inventory_fetch = scheduled_source_times(schedule.values(), state=previous, now=now)
    due = {k for k, v in schedule.items() if datetime.fromisoformat(v['next_fetch_at']) <= now}
    inventory_due = not previous or datetime.fromisoformat(previous['next_inventory_at']) <= now
    if inventory_fetch is not None:
        inventory_due = inventory_fetch <= now
        if not due and not inventory_due:
            return {**previous, 'status': 'not_due', 'network_requests': 0, 'changed': False}
    if previous and not due and not inventory_due and not force:
        return {**previous, 'status': 'not_due', 'network_requests': 0, 'changed': False}
    attempt = base / (now.strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8])
    database = attempt.with_suffix('.sqlite')
    if previous.get('database'):
        source = Path(previous['database']).resolve(strict=True)
        if not source.is_relative_to(base.resolve()):
            raise ValueError('ICA source database escaped its owned root')
        with sqlite3.connect(f'file:{source}?mode=ro', uri=True) as src, sqlite3.connect(database) as dst:
            src.backup(dst)
        from grocery_data.app.services.snapshot_retention import compact_candidate_copy
        compact_candidate_copy(database, attempt.with_name(attempt.name + '-raw'), now=now)
    engine = create_database_engine('sqlite:///' + database.resolve().as_posix())
    create_schema(engine)
    try:
        collector = GroceryCollector(create_session_factory(engine),
            FilesystemRawSnapshotStore(attempt.with_name(attempt.name + '-raw')))
        coverage = await collect(area, attempt, collector=collector,
            collect_flyers=False, discover_flyers=False, row_approved_offers=True,
            previous=previous.get('coverage'), only_store_ids=None if force or not previous else due)
        if coverage.get('inventory_error'):
            failure = {'status': 'inventory_failed_lkg_retained', 'changed': False,
                'error': coverage['inventory_error'], 'attempt': str(attempt),
                'attempted_at': now.isoformat(), 'price_universe_activated': False}
            atomic_write_bytes(base / 'latest-failure.json', json.dumps(failure).encode())
            if previous:
                from datetime import timedelta

                retained = {**previous, 'last_inventory_failure': failure,
                    'next_inventory_at': (now + timedelta(minutes=30)).isoformat(),
                    'store_schedule': {k: dict(v) for k, v in schedule.items()}}
                for account in due:
                    item = retained['store_schedule'][account]
                    failures = item.get('failed_attempts', 0) + 1
                    item.update(campaign_schedule([], now=now, failed_attempts=failures),
                        failed_attempts=failures, last_attempt_at=now.isoformat())
                atomic_write_bytes(pointer, json.dumps(retained, ensure_ascii=False, indent=2).encode())
            return {**previous, **failure}
        proposal = offer_store_proposal(coverage)
        schedules = dict(schedule)
        excluded = set(previous.get('excluded_store_ids', []))
        for row in coverage['stores']:
            account = row['ica_account_id']
            if row['area_membership'] != 'inside':
                continue
            if row['collection_status'] == 'not_due_retained':
                continue
            success = row['collection_status'] in {'success', 'confirmed_empty'}
            failures = 0 if success else schedules.get(account, {}).get('failed_attempts', 0) + 1
            prior_schedule = schedules.get(account, {})
            windows = row.get('campaign_windows', []) if success else prior_schedule.get('campaign_windows', [])
            last_success = row.get('last_success_at') if success else prior_schedule.get('last_success_at')
            row['last_success_at'] = last_success
            schedules[account] = {**campaign_schedule(windows, now=now,
                failed_attempts=failures), 'failed_attempts': failures,
                'campaign_windows': windows,
                'last_success_at': last_success, 'last_attempt_at': now.isoformat(),
                'status': row['collection_status']}
            acceptance = (row.get('row_approved_result') or {}).get('acceptance', {})
            if success and (not (row.get('row_approved_result') or {}).get('published')
                            or acceptance.get('shared_blockers')):
                excluded.add(account)
            elif success:
                excluded.discard(account)
        from datetime import timedelta
        ids = proposal['ica_offer_store_ids'] if proposal['inventory_approved'] else previous.get('ica_offer_store_ids', [])
        if area.mode == 'municipality':
            # Individual source-bound additions do not claim a complete inventory
            # and never modify the release's mandatory catalog contexts.
            ids = sorted(municipal_stores(coverage))
        current = {'status': 'partial_structured_source', 'changed': True,
            'inventory_checked_at': now.isoformat(),
            'database': str(database), 'coverage': coverage, 'store_schedule': schedules,
            'ica_offer_store_ids': ids, 'excluded_store_ids': sorted(excluded),
            'inventory_approved': proposal['inventory_approved'], 'observed_at': now.isoformat(),
            'next_inventory_at': (now + timedelta(hours=72 if coverage.get('inventory', {}).get('complete') else 1)).isoformat(),
            'image_analysis': False, 'complete': False, 'price_universe_activated': False}
        atomic_write_bytes(pointer, json.dumps(current, ensure_ascii=False, indent=2).encode())
        return current
    finally:
        engine.dispose()


async def run_optional_candidate_job(*, enabled: bool, city: str, root: Path,
                                     collect=collect_area_offers, extract=extract_area,
                                     visual_command=None) -> dict:
    """Caller must own the normal refresh lock; disabled means zero filesystem/network work."""
    if not enabled:
        return {"status":"disabled", "production_activation":False}
    slug = ''.join(c if c.isalnum() else '-' for c in city.casefold())
    base = root / slug
    engine = None
    try:
        base.mkdir(parents=True, exist_ok=True)
        pointer = base / 'latest-candidate.json'
        previous = json.loads(pointer.read_bytes()) if pointer.exists() else None
        attempt = base / (datetime.now(UTC).strftime('%Y%m%dT%H%M%S') + '-' + uuid4().hex[:8])
        database = attempt.with_suffix('.sqlite')
        engine = create_database_engine('sqlite:///' + database.resolve().as_posix())
        create_schema(engine)
    except Exception as exc:  # noqa: BLE001 - startup failures are optional too
        if engine is not None:
            engine.dispose()
        return {'status':'failed_candidate_lkg_retained','phase':'startup',
                'error':type(exc).__name__,'production_activation':False}
    try:
        collector = GroceryCollector(create_session_factory(engine), FilesystemRawSnapshotStore(attempt.with_name(attempt.name+'-raw')))
        coverage = await collect(GeographicArea(city=city), attempt, collector=collector,
            row_approved_offers=True, previous=previous.get('coverage') if previous else None)
        extraction = extract(coverage, attempt, database=database, visual_command=visual_command,
                             previous=previous.get('observations', []) if previous else [])
        if extract is extract_area:
            extraction = await import_area_extractions(coverage, extraction, attempt, database=database, collector=collector,
                previous=previous.get('observations', []) if previous else [])
        proposal = offer_store_proposal(coverage)
        current = {"status":"partial_candidate", "coverage":coverage,
                   "observations":extraction['observations'], "database":str(database),
                   "proposal":proposal, "extraction_complete":extraction['complete'],
                   "production_activation":False}
        inside = [s for s in coverage['stores'] if s['area_membership']=='inside']
        acceptable = proposal['inventory_approved'] and bool(inside) and all(
            s.get('row_approved_result',{}).get('published') for s in inside)
        if acceptable:
            atomic_write_bytes(pointer, json.dumps(current,ensure_ascii=False,indent=2).encode())
        return {"status":"partial_candidate" if acceptable else "failed_candidate_lkg_retained",
                "output":str(attempt),"candidate_pointer_updated":acceptable,
                "extraction_complete":extraction['complete'],"production_activation":False}
    except Exception as exc:  # noqa: BLE001 - optional source cannot stop working base
        return {"status":"failed_candidate_lkg_retained","error":type(exc).__name__,
                "output":str(attempt),"production_activation":False}
    finally:
        engine.dispose()


def structured_source_inputs(*, city: str, root: Path) -> dict:
    """Read only approved inventoried accounts; optional failure grants no data."""
    try:
        area, base = source_location(city, root)
        pointer = json.loads((base / 'structured-source.json').read_bytes())
        database = Path(pointer['database']).resolve(strict=True)
        if not database.is_relative_to(base.resolve()):
            return {}
        ids = frozenset(pointer['ica_offer_store_ids']) - frozenset(pointer.get('excluded_store_ids', []))
        if not ids:
            return {}
        result = {'ica_offer_store_ids': ids, 'ica_offer_database': database}
        if area.mode == 'municipality':
            if pointer['coverage']['area'] != area.model_dump(mode='json'):
                return {}
            stores = municipal_stores(pointer['coverage'])
            result['ica_offer_store_ids'] = ids & stores.keys()
            result['ica_municipal_stores'] = {k: v for k, v in stores.items() if k in ids}
        return result
    except (OSError, ValueError, KeyError, TypeError):
        return {}
