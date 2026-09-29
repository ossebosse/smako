"""Real source responses, with an explicit historical regression clock."""
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from grocery_data.app.connectors.ica import IcaConnector
from grocery_data.app.domain import GeographicArea, RawBatch, SourceStore
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.ica_area_offers import (
    RowApprovedOfferConnector,
    _RetainedStoreConnector,
)
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import (
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.app.storage.models import CatalogSnapshotModel, SourceProductModel


def source(account='1004598'):
    raw = RawBatch.model_validate_json((Path(__file__).parent/'fixtures/ica/area-20260916'/f'{account}.json').read_bytes())
    store = SourceStore(chain='ica', external_id=account, name='Retained official store', city='Lund',
        address='Emblas gata 23' if account=='1004598' else 'Stora Södergatan 57',
        coverage='offers_only', raw_reference='fixture:official-locator', source_fields={
            'store_id':'15172' if account=='1004598' else '2774',
            'offers_url':f'https://www.ica.se/erbjudanden/fixture-{account}/',
            'official_store_url':f'https://www.ica.se/butiker/fixture-{account}/'})
    return store, raw


@pytest.mark.parametrize('account,full_count,total', [('1004598',56,59),('1004339',45,49)])
async def test_partial_rows_keep_full_failure_denominator_and_observations(tmp_path, account, full_count, total):
    store, raw = source(account)
    engine=create_database_engine('sqlite:///'+str(tmp_path/'test.sqlite'))
    create_schema(engine); factory=create_session_factory(engine)
    collector=GroceryCollector(factory,FilesystemRawSnapshotStore(tmp_path/'raw'))
    connector=IcaConnector()
    original=await collector.collect_area(_RetainedStoreConnector(connector,store,raw,raw),GeographicArea(city='Lund'),scope_key='lund:offers')
    assert not original.promoted and original.metrics.products_parsed==full_count
    rows=RowApprovedOfferConnector(connector,store,raw,raw)
    rows.original_full_health=original.status.value
    result=await collector.collect_area(rows,GeographicArea(city='Lund'),scope_key='lund:ica:'+account+':offer-rows')
    assert result.promoted and result.metrics.parse_success_rate < .95
    assert result.metrics.products_parsed+result.metrics.products_quarantined==total
    assert rows.row_acceptance['full_parse']['parsed']==full_count
    assert rows.row_acceptance['full_parse']['denominator']==total
    with session_scope(factory) as session:
        original_db=session.get(CatalogSnapshotModel,original.snapshot_id)
        assert original_db.state=='rejected' and not original_db.is_active
        published=session.get(CatalogSnapshotModel,result.snapshot_id)
        assert published.metrics['acceptance_status']=='partial_row_approved'
        assert published.metrics['full_snapshot_health']=='degraded'
        products=list(session.scalars(select(SourceProductModel).where(SourceProductModel.catalog_snapshot_id==result.snapshot_id)))
        assert len(products)>0
        assert all(p.fetched_at==raw.documents[0].fetched_at and p.regular_price is None for p in products)
        assert all(p.source_fields['verified_store_scope'] for p in products)
        for p in products:
            if p.source_fields['variant_count'] != 1:
                assert p.source_fields['purchase_terms']['variant_selection'] == 'required'
                assert p.gtin is None and p.package_quantity is None
    from grocery_data.app.services.snapshot_manager import SnapshotManager, SnapshotValidationError
    manager = SnapshotManager(factory)
    pending = await collector.collect_area(rows, GeographicArea(city='Lund'), auto_promote=False,
        scope_key='lund:ica:'+account+':offer-rows')
    assert not pending.promoted
    assert manager.validate(pending.snapshot_id).id == pending.snapshot_id
    with session_scope(factory) as session:
        saved = session.scalar(select(SourceProductModel).where(SourceProductModel.catalog_snapshot_id==pending.snapshot_id))
        saved.source_fields = {**saved.source_fields, 'verified_store_scope': False}
    with pytest.raises(SnapshotValidationError, match='no longer qualifies'):
        manager.promote(pending.snapshot_id)
    assert manager.get(result.snapshot_id).is_active  # Failed candidate preserves LKG.
    await connector.aclose();engine.dispose()


@pytest.mark.parametrize('failure', ['schema','store','shared_condition'])
async def test_shared_failures_cannot_publish_partial_rows(tmp_path, failure):
    store, raw=source();data=raw.documents[0].json_payload()
    if failure=='schema':data['offers']['weeklyOffers']={}
    elif failure=='store':
        for row in data['offers']['weeklyOffers']:row['stores']=[{'accountNumber':'another-store','storeInd':True}]
    else:store=store.model_copy(update={'address':None})
    raw=raw.model_copy(update={'documents':(raw.documents[0].model_copy(update={'payload':json.dumps(data).encode()}),)})
    engine=create_database_engine('sqlite:///'+str(tmp_path/'test.sqlite'));create_schema(engine)
    collector=GroceryCollector(create_session_factory(engine),FilesystemRawSnapshotStore(tmp_path/'raw'))
    connector=IcaConnector();rows=RowApprovedOfferConnector(connector,store,raw,raw)
    result=await collector.collect_area(rows,GeographicArea(city='Lund'),scope_key='lund:ica:1004598:offer-rows')
    assert not result.promoted and rows.row_acceptance['shared_blockers']
    await connector.aclose();engine.dispose()
