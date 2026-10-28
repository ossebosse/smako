"""Method dispatch for the existing shared purchase and measured stock ledger.

These estimates only plan inputs. An issued operand, exact qualified source
and actual measured outputs remain separate gates; no price is calculated here.
"""
import json
from functools import lru_cache
from pathlib import Path

from app.services import egg_preparation as egg
from app.services.ingredient_normalizer import canonicalize_ingredient_name

MINT_LEAVES = "mint_leaf_trimming_estimate_v1"
MINT_OPERAND = "prepare:" + MINT_LEAVES
MINT_INPUT_KEY = "intake_all_shape_trimmed_mint"
MINT_LEAF_KEY = "intake_all_3f61df003596"


@lru_cache(maxsize=1)
def mint_reference():
    return json.loads((Path(__file__).parents[1] / 'data/nutrition/mint-leaf-trimming-v1.json').read_bytes())


def method_for(recipe, name):
    if egg.component(recipe, name):
        return egg.METHOD
    if (recipe is None or recipe.design is None or not name.casefold().startswith('mynt')
            or canonicalize_ingredient_name(name) != 'mynta'):
        return None
    ingredient = next((i for i in recipe.ingredients if i.canonical_name == 'mynta'), None)
    if (ingredient is not None and ingredient.unit == 'g' and ingredient.form == 'raw_edible'
            and MINT_OPERAND in (ingredient.product_requirements or ())
            and 'pack:' + MINT_LEAF_KEY in ingredient.product_requirements):
        return MINT_LEAVES
    return None


def source_name(method):
    return {egg.METHOD: 'ägg', MINT_LEAVES: 'mynta'}[method]


def source_requirement(method):
    return MINT_INPUT_KEY if method == MINT_LEAVES else None


def component_names(method):
    return {egg.METHOD: ('äggula', 'äggvita'), MINT_LEAVES: ('mynta',)}[method]


def input_quantity(method, amounts):
    if method == egg.METHOD:
        return egg.edible_input(amounts.get('äggula', 0), amounts.get('äggvita', 0))
    if method == MINT_LEAVES:
        r = mint_reference()
        return amounts.get('mynta', 0) * r['input_edible_fraction'] / r['reported_leaf_fraction']
    raise ValueError('Unknown reviewed ingredient preparation')


def estimated_outputs(method, quantity):
    if method == egg.METHOD:
        return {'äggula': quantity / 3, 'äggvita': quantity * 2 / 3}
    if method == MINT_LEAVES:
        r = mint_reference()
        return {'mynta': quantity * r['reported_leaf_fraction'] / r['input_edible_fraction']}
    raise ValueError('Unknown reviewed ingredient preparation')


def source_qualified(method, product, fact, candidate=None):
    if method == egg.METHOD:
        return egg.plain_source(product, fact)
    if method == MINT_LEAVES:
        from app.services.intake_product_links import compatible

        r = mint_reference()
        if candidate is not None:
            # ProductCandidate omits the brand/full source label. Keep those
            # fields from the actual source product and the already projected
            # usable quantity from the qualified candidate.
            product = product.model_copy(update={k: getattr(candidate, k) for k in (
                'usable_quantity', 'usable_unit', 'quantity_confidence')})
        return bool(compatible(MINT_INPUT_KEY, product, fact)
                    and product.package_unit == product.usable_unit == 'g'
                    and product.usable_quantity == round(product.package_quantity * r['input_edible_fraction'], 8))
    return False


def nutrition(method, name, product_id):
    # The experiment establishes a leaf-only yield example, no qualified
    # macro values for those leaves. Generic herb nutrients cannot supply it.
    return egg.nutrition(name, product_id) if method == egg.METHOD else None


def stock_name(method, component):
    return 'myntablad' if method == MINT_LEAVES and component == 'mynta' else component


def measured_outputs(preparation):
    if preparation.method == egg.METHOD:
        return {'äggula': preparation.yolk_g, 'äggvita': preparation.white_g}
    if preparation.method == MINT_LEAVES:
        return {'mynta': preparation.leaf_g}
    raise ValueError('Unknown reviewed ingredient preparation')


def stock_matches(origin, item, row):
    method = row.get('preparation')
    if origin['method'] == method:
        return item['name'] == stock_name(method, row['name'])
    # Picked leaves can satisfy a generic mint demand, but must never borrow
    # the generic leaves/minor-parts nutrient estimate for a constrained meal.
    return bool(origin['method'] == MINT_LEAVES and method is None
                and canonicalize_ingredient_name(row['name']) in {'mynta', 'myntablad'}
                and item['name'] == 'myntablad' and not row.get('nutrients'))
