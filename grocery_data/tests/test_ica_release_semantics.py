from decimal import Decimal
from pathlib import Path

from grocery_data.app.connectors.ica.parser import IcaParser
from grocery_data.app.domain import RawBatch, SourceStore
from grocery_data.app.services.offer_rows import row_blockers


def parsed(account,bms):
    batch=RawBatch.model_validate_json((Path(__file__).parent/'fixtures/ica/release-20260920'/f'{account}.json').read_bytes())
    store=SourceStore(chain='ica',external_id=account,name='Retained official source',city='Lund',
        raw_reference=batch.documents[0].url,coverage='offers_only',source_fields={'store_id':bms})
    result=IcaParser().parse_catalog(batch,['retained-source'],store)
    return {p.external_product_id:p for p in result.products}


def test_real_oats_butter_weight_and_reference_roles_survive_current_parser():
    rows=parsed('1088004','17883')
    oats=rows['5004145997']
    assert oats.regular_price is None and oats.sale_price is None
    assert oats.offers[0].price==30 and oats.offers[0].quantity==2
    assert oats.source_fields['price_evidence']['reference_regular']=='17.90'
    assert oats.comparison_price==10 and oats.package_quantity==1500
    assert not row_blockers(oats)
    butter=rows['5004146030']
    assert 'Gäller ej ekologisk' in butter.offers[0].description
    assert 'exact_single_variant_unverified' in row_blockers(butter)
    chicken=rows['5004145966']
    assert chicken.sale_unit=='kg' and chicken.offers[0].price==Decimal('87.9')
    assert chicken.package_text=='Ca 900 g' and 'Färsk' in chicken.offers[0].description
    assert chicken.regular_price is None and chicken.comparison_price is None
    assert chicken.source_fields['price_evidence']['reference_regular']=='101.93'
    assert 'fixed_purchase_package_unverified' in row_blockers(chicken)


def test_real_chicken_mince_sales_package_is_separate_from_800g_content():
    p=parsed('1086002','17864')['5004121462']
    assert p.sale_unit=='st' and p.package_quantity==800 and p.package_unit=='g'
    assert p.offers[0].price==62 and p.regular_price is None
    assert p.comparison_price==Decimal('77.50') and p.comparison_unit=='kg'
    assert p.offers[0].valid_from is None
    assert not row_blockers(p)
