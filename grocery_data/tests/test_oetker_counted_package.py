"""Manufacturer variants do not lend their default package mass to siblings."""
import hashlib
import json

import pytest

from grocery_data.app.services.product_declarations import parse_oetker_counted_package

GTIN = '5701073066478'


def document(*variants):
    body = ('<script id="__NEXT_DATA__" type="application/json">' + json.dumps(
        {'products': list(variants)}) + '</script>').encode()
    return body, {'url': 'https://www.oetker.se/produkter/p/gelatinblad',
                  'status': 200, 'observed_at': '2026-10-27T13:00:00Z',
                  'sha256': hashlib.sha256(body).hexdigest()}


def variant(**changes):
    return {'__typename': 'Product', 'productId': '1-54-006647', 'gtin': GTIN,
            'productTitle': 'Gelatinblad 12-p', 'fillingQuantity': '20 Gram', **changes}


def test_selects_exact_twelve_sheet_variant_not_default_ten_sheet_mass():
    body, source = document(variant(gtin='5701073066102', productTitle='Gelatinblad 10-p',
                                   fillingQuantity='17 Gram'), variant(), variant())
    row = parse_oetker_counted_package(body, source, GTIN)
    assert (row['package_quantity'], row['package_unit'], row['net_quantity']) == (12, 'st', 20)
    assert row['ingredients'] == '' and row['nutrition'] == {}


@pytest.mark.parametrize('rows', [
    [variant(gtin='5701073066102')],
    [variant(), variant(fillingQuantity='17 Gram')],
    [variant(fillingQuantity='20 ml')],
    [variant(productTitle='Gelatinblad')],
])
def test_missing_conflicting_or_unqualified_variant_is_rejected(rows):
    body, source = document(*rows)
    with pytest.raises(ValueError):
        parse_oetker_counted_package(body, source, GTIN)


def test_unverified_body_is_rejected():
    body, source = document(variant())
    with pytest.raises(ValueError, match='unverified'):
        parse_oetker_counted_package(body+b'changed', source, GTIN)
