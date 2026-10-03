import hashlib

import pytest

from grocery_data.app.services.product_declarations import parse_fontana_corroboration


def fixture():
    body = ('<h1>Oliver Kalamata utan kärna</h1>Tillgänglig i 290 g'
            '<h2>Näringsvärden per 100g</h2>Energi 1162 kJ/278 kcal Fett 29,5 g '
            'Kolhydrater 1,4 g Protein 1,7 g Köp denna produkt').encode()
    source = {'url':'https://www.fontana.se/produkt/oliver-kalamata-utan-karna/',
              'status':200, 'observed_at':'2026-10-03', 'sha256':hashlib.sha256(body).hexdigest()}
    identity = {'name':'Oliver Kalamata utan kärna', 'brand':'Fontana',
                'package_quantity':290, 'package_unit':'g',
                'parser':'dabas-consumer-quantity-v1', 'source':{'url':'https://www.dabas.com/productsheet/exact'}}
    return body, source, identity


def test_bound_table_retains_source_and_cannot_invent_gtin():
    r = parse_fontana_corroboration(*fixture())
    assert r['nutrition'] == {'kcal':278, 'fat_g':29.5, 'carbs_g':1.4, 'protein_g':1.7}
    assert 'gtin' not in r
    assert r['identity_source']['url'].endswith('/exact')


@pytest.mark.parametrize('changes', [{'name':'Oliver Halkidiki utan kärna'}, {'brand':'Other'},
                                   {'package_quantity':370}, {'package_unit':'ml'}])
def test_other_variant_or_package_rejected(changes):
    body, source, identity = fixture()
    with pytest.raises(ValueError):
        parse_fontana_corroboration(body, source, {**identity, **changes})


def test_changed_source_bytes_rejected():
    body, source, identity = fixture()
    with pytest.raises(ValueError):
        parse_fontana_corroboration(body+b'changed', source, identity)
