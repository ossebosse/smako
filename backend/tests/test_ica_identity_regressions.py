"""Real retained PriceUniverse pairs from the eight 2026-09-16 conflicts."""
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.models import Product
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import complete_identity_facts, identity_variant_conflicts

GROUPS = json.loads((Path(__file__).parent / 'fixtures/ica-identity-20260916.json').read_bytes())['groups']


@pytest.mark.parametrize('group', GROUPS, ids=lambda g: g['group'])
def test_real_identity_groups_never_transfer_prices_or_poison_original_facts(group):
    products = [Product.model_validate(p) for p in group['products']]
    before = [p.model_dump(mode='json') for p in products]
    source = products[0]
    key = (source.store_id, source.product_id)
    fact = ProductFacts(source='fixture-retained', source_product_id=source.product_id,
                        source_snapshot_id=source.source_provenance.source_snapshot_id)
    prepared = SimpleNamespace(universe=SimpleNamespace(products=products),
                               product_search_index=SimpleNamespace(groups={'g': list(range(len(products)))}))
    result = complete_identity_facts(prepared, {key: fact})
    assert 'identity_variant' not in result[key].conflicts
    assert [p.model_dump(mode='json') for p in products] == before
    reasons = identity_variant_conflicts(products)
    if source.gtin == '8719200006355':
        assert reasons == ('brand',)  # Milda vs Milda Culinesse: uncertain sub-brand, no guessed join.
        assert all((p.store_id, p.product_id) not in result for p in products[1:])
    else:
        assert reasons == ()
        assert all((p.store_id, p.product_id) in result for p in products)


@pytest.mark.parametrize('change,reason', [
    ({'brand': 'Different maker'}, 'brand'),
    ({'product_form': 'cooked'}, 'product_form'),
    ({'canonical_food': 'fish'}, 'canonical_food'),
    ({'name': 'Cheese 31%'}, 'percentage_variant'),
    ({'package_quantity': 250}, 'package'),
])
def test_real_gtin_cannot_override_contradictory_variant(change, reason):
    p = Product.model_validate(GROUPS[4]['products'][0]).model_copy(update={'name': 'Cheese 17%', 'product_form': 'raw'})
    assert reason in identity_variant_conflicts([p, p.model_copy(update=change)])
