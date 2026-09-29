"""Real document replay; historical review is an assertion oracle, never input."""
import base64
import copy
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

import pymupdf
import pytest

from grocery_data.app.connectors.willys import flyer_offers
from grocery_data.app.connectors.willys.flyer_inventory import approved_flyer_stores
from grocery_data.app.connectors.willys.flyer_text import caption_fields, period, qualify_document
from grocery_data.app.domain import RawBatch
from grocery_data.app.services.offer_rows import row_blockers

ROOT = Path(__file__).parents[2] / 'reports/willys-flyers-20260923'


@pytest.fixture(scope='module', params=[('2863','1281',34,29), ('2352','1280',112,81)])
def source(request):
    identity,code,count,accepted=request.param
    inventory=json.loads((ROOT/f'inventory-{code}/inventory.json').read_bytes())
    raw=RawBatch.model_validate_json((ROOT/f'live-{identity}.json').read_bytes())
    return approved_flyer_stores(inventory)[identity],inventory,raw,count,accepted


def test_real_editions_without_register_use_general_rules_and_match_independent_oracle(source,monkeypatch):
    store,inventory,raw,count,accepted=source
    # Historical independently reviewed amounts are loaded for assertions only.
    oracle=json.loads(flyer_offers.REVIEW.read_bytes())
    monkeypatch.setattr(flyer_offers,'REVIEW',Path('deliberately-absent-review.json'))
    c=flyer_offers.AutomaticWillysFlyerConnector(store=store,inventory=inventory,raw=raw)
    parsed=c.parse_catalog(raw,['listing','document'],store)
    assert len(c.review['ads'])==count
    assert len(parsed.products)==accepted > 3
    assert c.review['automation']['existing_manual_advertisements']==0
    expected=next(x for x in oracle if x['pdf_sha256']==c.review['pdf_sha256'])
    for ad in c.review['ads']:
        if ad['status']!='qualified':continue
        old=next(o for o in expected['ads'] if o['page']==ad['page'] and o['bbox']==ad['bbox'])
        if ad.get('price_basis_unit') == 'kg':
            # Independently read current source quotes, assertions only.
            quotes = {'FLÄSKYTTERFILÉ':'69.9','GOUDA':'49.9','ROYAL GALA, GRANNY SMITH':'19.9',
                      'HELGDAG':'79.9','HEL MAJSKYCKLING':'59.9','LAMMFRAMDEL MED BEN':'89.9',
                      'KALVHÖGREV I BIT':'159'}
            assert Decimal(ad['price']) == Decimal(quotes[ad['title']])
            assert ad['package_quantity'] is ad['package_unit'] is None
            assert ad['exact_checkout_supported'] is False
            assert ad['text'] == old['text']
            continue
        if ad['title'] == 'FUSILLI, PENNE RIGATE':
            assert ad['names'] == ['Fusilli','Penne rigate']
            assert ad['package_quantity'] == 1000 and ad['package_unit'] == 'g'
            assert Decimal(ad['price']) == Decimal('25.9')
            continue
        if ad.get('open_variant_group'):
            # Independently checked printed total/count; assertions, never importer input.
            expected_groups = {
                'CHIPS, OSTSNACKS': ('38',2), 'SKIVAT SMÖRGÅSPÅLÄGG':('25.9',1),
                'BEARNAISE':('17.9',1), 'PIZZATOPPING':('30',2), 'FÄRSK PIZZA':('99',3),
                'SALAMI SNACKS, CHIPS, STICKS':('38',2), 'SKIVAT SMÖRGÅS- PÅLÄGG':('50',2),
                'MJUKOST':('37.9',1), 'SHOT':('29.9',1), 'BEEF BURGER':('99.9',1),
                'KEBAB':('79',2), 'PIZZA':('85',2), 'KYLD SÅS':('17.9',1),
                'VEGETARISKA MÅLTIDSDELAR':('29.9',1), 'TORTILLACHIPS':('20',2),
                'GLUTENFRITT BRÖD':('26.9',1), 'POMMES':('45',2),
                'FLÄCKBORTTAGNING':('52.9',1), 'BABYTVÄTT':('55',2), 'GLASS':('34.9',1),
                'CHOKLADKAKA':('48',2),
            }
            assert (ad['price'],ad['required_packages']) == expected_groups[ad['title']]
            assert ad['text'] == old['text']
            assert ad['purchase_terms']['variant_selection'] == 'required'
            assert not ad['exact_checkout_supported']
            if ad['purchase_terms']['variant_package_minimum']:
                assert ad['package_quantity'] is None  # No invented midpoint.
            continue
        assert old['status'] in {'qualified', 'duplicate'}
        for k in ('required_packages','member_only','max_quantity','package_unit','valid_from','valid_to'):
            assert old[k]==ad[k],(ad['title'],k)
        for k in ('price','package_quantity'):
            assert Decimal(str(old[k]))==Decimal(str(ad[k])),(ad['title'],k)
        assert old['text']==ad['text']
    assert all(not row_blockers(p) for p in parsed.products)
    assert all(p.regular_price is p.sale_price is p.gtin is None for p in parsed.products)
    assert all(p.fetched_at==min(d.fetched_at for d in raw.documents) for p in parsed.products)
    reasons=Counter(a.get('reason') for a in c.review['ads'] if a['status']!='qualified')
    assert reasons['variant_range_or_approximate_quantity_requires_review']
    assert sum(reasons.values()) > 0


def test_new_hash_does_not_require_whole_document_approval(source,monkeypatch):
    store,inventory,raw,_,accepted=source
    # Synthetic metadata-only PDF change, not a claim of a real new campaign.
    value=raw.documents[1].json_payload()
    with pymupdf.open(stream=base64.b64decode(value['pdf_base64']),filetype='pdf') as doc:
        doc.set_metadata({'subject':'synthetic unknown digest acceptance probe'})
        data=doc.tobytes()
    value.update(pdf_base64=base64.b64encode(data).decode(),sha256=hashlib.sha256(data).hexdigest())
    changed=raw.model_copy(update={'documents':(raw.documents[0],raw.documents[1].model_copy(update={'payload':json.dumps(value).encode()}))})
    monkeypatch.setattr(flyer_offers,'REVIEW',Path('deliberately-absent-review.json'))
    c=flyer_offers.AutomaticWillysFlyerConnector(store=store,inventory=inventory,raw=changed)
    assert len(c.parse_catalog(changed,['listing','document'],store).products)==accepted
    assert c.observed==min(d.fetched_at for d in raw.documents)


def test_pdf_viewer_disagreement_is_page_isolated(source,monkeypatch):
    store,inventory,raw,_,_=source
    monkeypatch.setattr(flyer_offers,'REVIEW',Path('absent-review.json'))
    v=raw.documents[0].json_payload();v['pageTexts'][1]+=' NEW UNBOUND CONDITION '
    changed=raw.model_copy(update={'documents':(raw.documents[0].model_copy(update={'payload':json.dumps(v).encode()}),raw.documents[1])})
    c=flyer_offers.AutomaticWillysFlyerConnector(store=store,inventory=inventory,raw=changed)
    assert all(a['status']!='qualified' for a in c.review['ads'] if a['page']==2)
    assert any(a['status']=='qualified' for a in c.review['ads'] if a['page']!=2)


def test_campaign_periods_and_explicit_short_days_not_whole_week():
    assert period('Priserna gäller på Willys från måndag 28/12 t o m söndag 3/1 2027')==('2026-12-28','2027-01-03')
    text='TEST\nBRAND • 500g • Jämförpris 20:00 kr/kg • Gäller endast 21–23 september • Max 2 köp/hushåll'
    ad=caption_fields({'text':text,'title':'TEST'},('2026-09-21','2026-09-27'))
    assert (ad['valid_from'],ad['valid_to'],ad['max_quantity'])==('2026-09-21','2026-09-23',2)
    for tail in (' • Aktivera i appen', ' • Max 2 kg/hushåll', ' • Annat undantag'):
        with pytest.raises(ValueError):caption_fields({'text':text+tail,'title':'TEST'},('2026-09-21','2026-09-27'))


def test_descriptor_variants_do_not_authorize_open_ranges_or_unknown_conditions():
    text='SMÖR & RAPS\nBRAND • 600g • Normalsaltat • Extrasaltat • Jämförpris 74:83 kr/kg'
    row=caption_fields({'text':text,'title':'SMÖR & RAPS'},('2026-09-21','2026-09-27'))
    assert row['names']==['Smör & raps Normalsaltat','Smör & raps Extrasaltat']
    for tail in (' • Aktivera kupong',' • 400-600g',' • Max 2 kg/hushåll'):
        with pytest.raises(ValueError):
            caption_fields({'text':text+tail,'title':'SMÖR & RAPS'},('2026-09-21','2026-09-27'))


def test_synthetic_new_campaign_text_uses_new_dates_and_keeps_uncertainty(source):
    _,_,raw,_,accepted=source
    class Page:
        def __init__(self,p):self.p,self.rect=p,p.rect
        def get_text(self,mode=None):
            v=self.p.get_text(mode) if mode else self.p.get_text()
            if isinstance(v,str):return v.replace('21/9','28/9').replace('27/9','4/10')
            return v  # product text unchanged; only document footer clock is simulated
    with pymupdf.open(stream=base64.b64decode(raw.documents[1].json_payload()['pdf_base64']),filetype='pdf') as doc:
        listing=copy.deepcopy(raw.documents[0].json_payload())
        listing['pageTexts']=[t.replace('21/9','28/9').replace('27/9','4/10') for t in listing['pageTexts']]
        result=qualify_document([Page(p) for p in doc],listing)
    assert (result['valid_from'],result['valid_to'])==('2026-09-28','2026-10-04')
    assert sum(len(a['names']) for a in result['ads'] if a['status']=='qualified')==accepted
    assert all(a['valid_to']=='2026-10-04' for a in result['ads'] if a['status']=='qualified')
    assert any(a['status']=='quarantine' for a in result['ads'])

def test_retained_legacy_fallback_does_not_duplicate_parser_blocks(source):
    store,inventory,raw,count,_=source
    c=flyer_offers.AutomaticWillysFlyerConnector(store=store,inventory=inventory,raw=raw)
    assert len(c.review['ads'])==count
    parsed=c.parse_catalog(raw,['listing','document'],store)
    assert len(parsed.products)==(31 if store.external_id=='2863' else 89)
    assert len({p.external_product_id for p in parsed.products})==len(parsed.products)


def test_new_unbound_critical_condition_stops_page_not_other_pages(source):
    _,_,raw,_,_=source
    class Page:
        def __init__(self,p,inject):self.p,self.rect,self.inject=p,p.rect,inject
        def get_text(self,mode=None):
            v=self.p.get_text(mode) if mode else self.p.get_text()
            if not self.inject:return v
            if isinstance(v,str):return v+' Kupong krävs '
            v['blocks'].append({'type':0,'bbox':(0,0,100,10),'lines':[{'spans':[{'text':'Kupong krävs','font':'Unknown','size':8}]}]})
            return v
    with pymupdf.open(stream=base64.b64decode(raw.documents[1].json_payload()['pdf_base64']),filetype='pdf') as doc:
        listing=copy.deepcopy(raw.documents[0].json_payload());listing['pageTexts'][1]+=' Kupong krävs '
        result=qualify_document([Page(p,i==1) for i,p in enumerate(doc)],listing)
    assert all(a.get('reason')=='unbound_critical_condition_on_page' for a in result['ads'] if a['page']==2)
    assert any(a['status']=='qualified' for a in result['ads'] if a['page']!=2)

def test_deposit_label_below_price_requires_review_even_without_caption_deposit():
    from grocery_data.app.connectors.willys.flyer_text import price_blocks
    price={'bbox':[100,100,130,140],'text':'1000',
           'spans':[{'font':'GothamSerif-Price','text':'10'},{'font':'GothamSerif-Price','text':'00'}]}
    unit={'bbox':[100,90,135,98],'text':'Per förp','spans':[]}
    deposit={'bbox':[100,145,135,150],'text':'+pant','spans':[]}
    assert price_blocks([price,unit])[0]['error'] is None
    assert price_blocks([price,unit,deposit])[0]['deposit_unknown'] is True
    assert price_blocks([price,unit,deposit])[0]['error'] is None


def test_weight_unit_case_and_history_are_not_conflicting_units():
    from grocery_data.app.connectors.willys.flyer_text import price_blocks
    block={'bbox':[0,0,100,100], 'text':'SPARA 10 PER KG\n7990\nPer kg',
           'spans':[{'font':'GothamSerif-Price','text':'79'},{'font':'GothamSerif-Price','text':'90'}]}
    assert price_blocks([block])[0]['error'] is None
    ad=caption_fields({'title':'OST','text':'OST\nBRAND • Ca 1kg • 35% • Jämförpris 79:90 kr/kg • Lägsta 30-dgrspris 94:90 kr/kg'},('2026-09-21','2026-09-27'))
    assert ad['package_quantity'] is None and ad['approximate_package_quantity_g']==1000
    assert ad['comparison_price']=='79.90'


def test_rate_arithmetic_cannot_be_relabelled_as_package_contract(source):
    store,inventory,raw,_,_=source
    c=flyer_offers.AutomaticWillysFlyerConnector(store=store,inventory=inventory,raw=raw)
    ps=c.parse_catalog(raw,['listing','document'],store).products
    p=next(p for p in ps if p.sale_unit=='kg')
    fields=copy.deepcopy(p.source_fields)
    fields['document_product_binding']['comparison_price']='1.00'
    assert 'fixed_purchase_package_unverified' in row_blockers(p.model_copy(update={'source_fields':fields}))
    assert not row_blockers(p)
