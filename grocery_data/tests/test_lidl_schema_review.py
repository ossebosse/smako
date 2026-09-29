"""Contract review cannot erase drift or renew saved price observations."""
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from grocery_data.app.connectors.lidl import LidlConnector, LidlParser
from grocery_data.app.domain import (
    Chain,
    ConnectorStatus,
    GeographicArea,
    RawBatch,
    RawFetch,
    SourceCollectionAudit,
    SourcePolicy,
)
from grocery_data.app.monitoring import SchemaDiff, diff_json_schemas
from grocery_data.app.services.collector import GroceryCollector, _review_schema_diff
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import DatabaseReplayService
from grocery_data.app.services.snapshot_manager import SnapshotManager, SnapshotValidationError
from grocery_data.app.storage import (
    SnapshotRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)

OBSERVED = datetime(2026, 8, 20, 12, tzinfo=UTC)
FIXTURE = Path(__file__).parents[1] / "app/connectors/lidl/fixtures/offer_samples.json"


class SavedLidl(LidlConnector):
    def __init__(self, *, optional_change=False, unknown_change=False):
        self.parser = LidlParser()
        self.parser_version = self.parser.parser_version
        self.optional_change = optional_change
        self.unknown_change = unknown_change

    def collection_policy_audit(self):
        return SourceCollectionAudit(source_policy=SourcePolicy.ALLOW, operator_opt_in=False)

    def batch(self, kind):
        payload = json.loads(FIXTURE.read_bytes())
        payload['items'] = payload['items'][:1]
        payload['numFound'] = payload['fetchsize'] = 1
        data = payload['items'][0]['gridbox']['data']
        if kind == 'offer_context_probe':
            if self.optional_change:
                data['price'] = {'basePrice': {'prefix': '', 'text': '94 kr/kg'}}
                data['seals'] = []
            else:
                data['price'] = {}
                data['seals'] = [{'altText': 'fixture', 'image': 'fixture'}]
        if self.unknown_change and kind == 'offer_page':
            data['unverifiedPrice'] = 123
        return RawBatch(chain=self.chain, documents=(RawFetch(
            chain=self.chain, kind=kind, method='GET',
            url='https://www.lidl.se/q/api/search', http_status=200,
            content_type='application/json', payload=json.dumps(payload).encode(),
            connector_version=self.connector_version, fetched_at=OBSERVED,
            store_external_id='public-default-region' if kind == 'offer_page' else None,
            page_number=0,
        ),))

    async def fetch_stores(self, area):
        return self.batch('offer_context_probe')

    async def fetch_catalog(self, store):
        return self.batch('offer_page')

    async def aclose(self):
        pass


@pytest.fixture
def services(tmp_path):
    engine = create_database_engine('sqlite+pysqlite:///:memory:')
    create_schema(engine)
    factory = create_session_factory(engine)
    raw = FilesystemRawSnapshotStore(tmp_path / 'raw')
    yield factory, GroceryCollector(factory, raw), SnapshotManager(factory), raw
    engine.dispose()


@pytest.mark.asyncio
async def test_review_candidate_keeps_raw_diff_and_manual_validation_rechecks(services):
    factory, collector, manager, raw = services
    baseline = await collector.collect_area(SavedLidl(), GeographicArea(city='Sverige'))
    assert baseline.promoted
    candidate = await collector.collect_area(
        SavedLidl(optional_change=True), GeographicArea(city='Sverige'), auto_promote=False,
    )
    assert candidate.status == ConnectorStatus.HEALTHY
    assert not candidate.promoted
    row = manager.validate(candidate.snapshot_id)
    assert row.metrics['schema_diff']['added']
    assert row.metrics['schema_diff']['removed']
    assert row.metrics['effective_schema_diff'] is None
    with session_scope(factory) as session:
        assert SnapshotRepository(session).active(Chain.LIDL, scope_key='sverige').id == baseline.snapshot_id
    replay = await DatabaseReplayService(factory, raw).replay_snapshot(
        SavedLidl(), candidate.snapshot_id, promote=False,
    )
    assert replay.status == ConnectorStatus.HEALTHY
    assert replay.network_requests == 0
    manager.validate(replay.replay_snapshot_id)
    with session_scope(factory) as session:
        from sqlalchemy import select

        from grocery_data.app.storage.models import ProductModel
        products = session.scalars(select(ProductModel).where(
            ProductModel.catalog_snapshot_id == replay.replay_snapshot_id,
        )).all()
        assert products and all(p.observed_at == OBSERVED for p in products)


@pytest.mark.asyncio
async def test_unknown_price_schema_still_rejects_and_retains_lkg(services):
    factory, collector, manager, _ = services
    baseline = await collector.collect_area(SavedLidl(), GeographicArea(city='Sverige'))
    candidate = await collector.collect_area(
        SavedLidl(optional_change=True, unknown_change=True), GeographicArea(city='Sverige'),
    )
    assert not candidate.promoted
    assert candidate.status == ConnectorStatus.DEGRADED
    assert candidate.active_snapshot_id == baseline.snapshot_id
    row = manager.get(candidate.snapshot_id)
    assert any('unverifiedPrice' in p for p in row.metrics['effective_schema_diff']['added'])
    with session_scope(factory) as session:
        row = SnapshotRepository(session).get(candidate.snapshot_id)
        row.state = 'health_checked'
        row.metrics = {**row.metrics, 'effective_schema_diff': None}
    with pytest.raises(SnapshotValidationError, match='schema changed'):
        manager.promote(candidate.snapshot_id)


def test_review_does_not_apply_to_old_parser_other_chain_or_type_changes():
    optional = SchemaDiff(added=('offer_context_probe:$[].items[].gridbox.data.storeEndDate',))
    assert _review_schema_diff(Chain.LIDL, 'lidl-parser-v3', optional) == optional
    assert _review_schema_diff(Chain.ICA, LidlParser.parser_version, optional) == optional
    typed = diff_json_schemas({'price': 12.5}, {'price': 'unknown'})
    assert _review_schema_diff(Chain.LIDL, LidlParser.parser_version, typed) == typed
