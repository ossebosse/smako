import json
from types import SimpleNamespace

import pytest
from app.providers.ica_area_offers import IcaAreaOfferProvider

from backend.tests.test_ica_area_offer_provider import Base, Own


@pytest.mark.parametrize('locality', ['Södra Sandby', 'Genarp', 'Veberöd'])
@pytest.mark.parametrize('conflict', [None, 'address', 'source_account', 'source_snapshot', 'source_internal_store'])
async def test_municipal_provider_uses_exact_identity_across_postal_localities(tmp_path, locality, conflict):
    class MunicipalOwn(Own):
        async def find_offer_stores_in_locality(self, city):
            assert city == locality
            return [(await super().find_offer_stores(''))[0].model_copy(update={
                'city': locality, 'price_context_type': 'physical_store'})]
        async def get_offers(self, store):
            product = (await super().get_offers(store))[0]
            return [product.model_copy(update={'source_provenance': product.source_provenance.model_copy(
                update={'provider_store_id': 'wrong' if conflict == 'source_internal_store' else store})})]
    official = SimpleNamespace(city=locality, address='Wrong' if conflict == 'address' else 'Fixture 1', postal_code='22476')
    provider = IcaAreaOfferProvider(Base(), MunicipalOwn(), database=tmp_path/'none.sqlite', city='Lund',
        account_ids=frozenset({'1'}), municipal_stores={'1':official})
    provider.evidence = {'fixture': {'parser_version':'ica-parser-v7','external_product_id':'fixture',
        'source_fields':json.dumps({'variant_count':1}), 'external_id':'wrong' if conflict == 'source_account' else '1',
        'snapshot_id':'wrong' if conflict == 'source_snapshot' else 'fixture', 'scope_key':'lund:ica:1:offer-rows'}}
    stores = await provider.find_stores('22350')
    assert bool(stores) is (conflict is None)
    if stores:
        assert stores[0].city == locality
        assert len(await provider.get_store_products(stores[0].store_id)) == 1


@pytest.mark.parametrize('corrupt', [False, True])
async def test_optional_hemkop_database_failure_keeps_mandatory_base(tmp_path, corrupt):
    from app.services.production_price_universe_build import build_city_price_universe

    from backend.tests.test_own_provider_grocery_data_contract import _contract_database
    from backend.tests.test_production_price_universe_build import _copy_sqlite_database
    source, _ = _contract_database()
    try:
        database = tmp_path/'base.sqlite'; _copy_sqlite_database(source, database)
        optional = tmp_path/'hemkop.sqlite'
        if corrupt:
            optional.write_text('synthetic broken database', encoding='utf-8')
        result = await build_city_price_universe(database, 'Lund', '22350', None,
            tmp_path/'candidate.json', 48, hemkop_offer_database=optional,
            hemkop_municipal_stores={'fixture':SimpleNamespace(city='Dalby',address='Fixture',postal_code='24750')})
        assert result['status']=='PASS' and result['raw_products']==1 and result['database_unchanged']
    finally:
        source.dispose()
