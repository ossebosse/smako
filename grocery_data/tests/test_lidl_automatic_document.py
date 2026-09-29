"""Real retained sources; expected records are assertions, never parser input."""
import json
from pathlib import Path

import pymupdf
import pytest

from grocery_data.app.connectors.lidl import municipal_offers
from grocery_data.app.connectors.lidl.document_qualification import METHOD
from grocery_data.app.connectors.lidl.municipality_inventory import approved_lidl_stores
from grocery_data.scripts.collect_lidl_municipality import retained_bundle

ROOT = Path(__file__).parents[2] / 'reports/lidl-municipality-20260923/package-live-verification'
# Independently checked PDF text prices/quantities. These are not supplied to qualification.
EXPECTED = {'11209202': ('99.0', '1 kg'), '11007943': ('54.9', '750 g'),
            '11137582': ('32.9', '350 g'), '11005814': ('27.9', '500 g'),
            '11208814': ('69.9', '750 ml'), '11137360': ('24.9', '1 l'),
            '11137373': ('44.9', '250 g'), '11137670': ('24.9', '200 g'),
            '11039774': ('11.9', '195 ml'), '11510284': ('44.9', '180 g'),
            '11115868': ('39.9', '200 g'), '11037637': ('29.9', '500 g'),
            '11137326': ('19.9', '100 g'), '11219137': ('29.9', '150 g'),
            '11039253': ('24.9', '2x 100 g'), '11137335': ('64.9', '240 g'),
            '11137878': ('9.9', '100 g'), '11214016': ('159.0', '1,8 kg'),
            '11218552': ('17.9', '500 g'), '11219261': ('13.9', '540 g'),
            '11220599': ('64.9', '600 g')}
EXPECTED.update({'11217807':('49.9','1,1 kg'), '11219129':('27.9','500 g'),
                 '11029883':('11.9','/st'), '11150856':('26.9','/kg'), '11217379':('69.9',None)})


def parse(mutate=None, pdf=None):
    bundle = retained_bundle(ROOT / 'source')
    batch = bundle['catalog']
    if mutate:
        documents = []
        for document in batch.documents:
            payload = document.json_payload()
            for item in payload['items']:
                row = item['gridbox']['data']
                if str(row['productId']) == '11209202':
                    mutate(row)
            documents.append(document.model_copy(update={'payload': json.dumps(payload).encode()}))
        batch = batch.model_copy(update={'documents': tuple(documents)})
    inv = json.loads((ROOT / '1281/inventory.json').read_bytes())
    c = municipal_offers.MunicipalLidlOfferConnector(store=approved_lidl_stores(inv)['0163'],
        registry=inv['registry'], catalog=batch, publication=bundle['publication'], pdf=pdf or bundle['pdf'])
    return c.parse_catalog(batch, ['retained'] * len(batch.documents), c.store), c


def test_all_independently_verified_foods_qualify_without_manual_registry(monkeypatch):
    monkeypatch.setattr(municipal_offers, 'REVIEW', Path('absent-manual-register.json'))
    result, c = parse()
    assert {p.external_product_id for p in result.products} == EXPECTED.keys()
    assert len(result.products) == 26 and len(result.failures) == 354
    for p in result.products:
        assert (str(p.offers[0].price), p.package_text) == EXPECTED[p.external_product_id]
        assert p.source_fields['document_product_binding']['identity_method'] == METHOD
        assert p.offers[0].valid_from.isoformat() == '2026-09-21'
        assert p.offers[0].valid_to.isoformat() == '2026-09-27'
        assert p.regular_price is p.sale_price is p.member_price is None
        assert p.gtin != p.external_product_id
    assert c.row_acceptance['full_parse']['parsed'] == 378


@pytest.mark.parametrize('mutate', [
    lambda r: r['regionsPrices']['1']['currentPrice'].update(price=89),
    lambda r: r['regionsPrices']['1']['currentPrice']['packaging'].update(text='900 g'),
    lambda r: r.update(title='Kalkonlårfilé', fullTitle="Butcher's Kalkonlårfilé"),
    lambda r: r.update(fullTitle='Another same-price variant'),
    lambda r: (r['brand'].update(name='Butcher'), r.update(title="'s Kalkonbröstfilé")),
    lambda r: r['keyfacts'].update(description='Max 1 förp./hushåll'),
    lambda r: r['keyfacts'].update(description='Aktivera personlig kupong'),
    lambda r: r.update(storeEndDate=1789855199),
    lambda r: r['regionsPrices']['1'].update(currentLidlPlusPrice={
        'price': r['regionsPrices']['1']['currentPrice'].copy(), 'lidlPlusText': 'Med Lidl Plus'}),
    lambda r: r['regionsPrices']['1']['currentPrice'].update(
        priceLegendName='**', priceLegendText='Gäller endast i en annan butik'),
])
def test_wrong_price_variant_package_membership_limit_expiry_or_scope_isolated(mutate):
    result, _ = parse(mutate)
    assert '11209202' not in {p.external_product_id for p in result.products}
    assert len(result.products) == len(EXPECTED)-1


def test_unknown_pdf_digest_does_not_inherit_old_manual_approvals():
    bundle = retained_bundle(ROOT / 'source')
    with pymupdf.open(stream=bundle['pdf'], filetype='pdf') as doc:
        doc.set_metadata({'subject': 'synthetic digest change, not a real next campaign'})
        pdf = doc.tobytes()
    result, _ = parse(pdf=pdf)
    assert {p.external_product_id for p in result.products} == EXPECTED.keys()


def test_retained_real_week40_text_bindings_cannot_be_bought_before_start():
    from grocery_data.app.domain import RawFetch

    root = ROOT.parents[1] / 'offer-coverage-20260924'
    bundle = retained_bundle(root / 'lidl-live-source')
    inv = json.loads((ROOT / '1281/inventory.json').read_bytes())
    c = municipal_offers.MunicipalLidlOfferConnector(store=approved_lidl_stores(inv)['0163'],
        registry=inv['registry'], catalog=bundle['catalog'],
        publication=RawFetch.model_validate_json((root/'lidl-holdout/publication.json').read_bytes()),
        pdf=(root/'lidl-holdout/publication.pdf').read_bytes())
    result = c.parse_catalog(c.catalog, ['retained']*len(c.catalog.documents), c.store)
    assert not c.review['products']  # old edition's approvals were not inherited
    assert {d['product_id'] for d in c.document_decisions if d['status']=='qualified'} == {
        '11214169', '11218649', '11316535', '11218942', '11038413'}
    assert not result.products  # actual observations predate 28 September


def test_publication_request_and_download_identity_cannot_be_swapped(tmp_path):
    from grocery_data.app.connectors.lidl.document_qualification import national_metadata

    bundle=retained_bundle(ROOT/'source')
    publication=bundle['publication']
    with pytest.raises(ValueError, match='scope_unverified'):
        national_metadata(publication.model_copy(update={'query':{'flyer_identifier':'wrong-publication'}}))
    (tmp_path/'publication.json').write_bytes((ROOT/'source/publication.json').read_bytes())
    (tmp_path/'pdf-source.json').write_bytes((ROOT/'source/pdf-source.json').read_bytes())
    (tmp_path/'publication.pdf').write_bytes(b'a different downloaded document')
    with pytest.raises(ValueError, match='acquisition_binding_changed'):
        retained_bundle(tmp_path)


def test_detached_package_needs_unique_geometric_owner_not_matching_amount():
    from types import SimpleNamespace

    from grocery_data.app.connectors.lidl.document_qualification import detached_package
    label={'type':0,'lines':[{'spans':[{'font':'LidlFontPro-Bold','text':'1,1 kg','bbox':[10,10,50,20]}]}]}
    page=SimpleNamespace(get_text=lambda _: {'blocks':[label]})
    caption={'bbox':[10,40,60,80]}
    assert detached_package(page,caption,[(caption,'A',[])])['text']=='1,1 kg'
    for other in ({'bbox':[15,50,60,90]}, {'bbox':[15,30,60,70]}):
        with pytest.raises(ValueError,match='not_unique'):
            detached_package(page,caption,[(caption,'A',[]),(other,'B',[])])
    with pytest.raises(ValueError,match='not_unique'):
        detached_package(page,{'bbox':[300,40,350,80]},[(caption,'A',[])])
