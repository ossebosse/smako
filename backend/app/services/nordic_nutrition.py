"""Reviewed generic plain-food estimates. Never product/allergen declarations."""
import json
import math
import re
from functools import lru_cache
from pathlib import Path

from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.nutrition_reference import NutritionEvidence

PATH = Path(__file__).parents[1] / 'data/nutrition/nordic-20261015.json'


@lru_cache(maxsize=1)
def data():
    return json.loads(PATH.read_bytes())


def plain_food_evidence(product, name, fact):
    if fact and (fact.conflicts or fact.nutrition):
        return None  # Partial/contradictory declarations remain visible.
    canonical = canonicalize_ingredient_name(name)
    label = ' '.join(product.name.casefold().split())
    category = (getattr(product, 'category', None) or '').casefold()
    composition = ' '.join(fact.ingredients).casefold() if fact else ''
    patterns = {
        'oregano': r'oregano(?: torkad| burk| påse| ekologisk| eko)*',
        'paprikapulver': r'paprikapulver(?: malen| mild| milt| söt| burk| påse| ekologisk| eko)*',
        'svartpeppar': r'svartpeppar(?: malen| hel| grovmalen| burk| påse| ekologisk| eko)*',
        'cayennepeppar': r'cayennepeppar(?: malen| burk| påse| ekologisk| eko)*',
        'ströbröd': r'ströbröd',
        'fetaost': r'fetaost(?: block| original| eko| ekologisk)*',
    }
    if canonical not in patterns or not re.fullmatch(patterns[canonical], label):
        return None
    if canonical in {'oregano', 'paprikapulver', 'svartpeppar', 'cayennepeppar'} and (
                re.search(r'färsk|frukt|grönsak|fryst|kryddväxt', category)
                or not ('krydd' in category or re.search(r'burk|påse|torkad|pulver', label))
                or composition and re.search(r'salt|socker|olja|smör|mjölk|blandning', composition.split('kan innehålla')[0])):
        return None
    if canonical in {'oregano', 'paprikapulver', 'svartpeppar', 'cayennepeppar'} and composition:
        words = set(re.findall(r'[^\W\d_]+', composition.split('kan innehålla')[0]))
        allowed = {canonical, 'ingredienser', 'ekologisk', 'ekologiska', 'malen', 'hel', 'mald'}
        if canonical == 'paprikapulver':
            allowed |= {'paprika'}
        if not words <= allowed:
            return None
    if canonical == 'fetaost' and (not re.search(r'mejeri|ost', category) or re.search(r'olja|krydd|soja|kokos|vatten', composition)):
        return None
    if canonical == 'ströbröd' and re.search(r'glutenfri|panko|krydd|ost|fullkorn|råg', composition):
        return None
    row = data()['foods'][canonical]
    values = row['nutrition']
    if (set(values) != {'kcal', 'protein_g', 'carbs_g', 'fat_g'} or row['unit'] != 'g'
            or row['basis_quantity'] != 100 or any(not math.isfinite(v) or v < 0 for v in values.values())):
        raise ValueError('Invalid reviewed Nordic nutrition reference')
    source = row.get('attribution', data()['attribution'])
    proof = {'kind': 'generic_reference', 'food_id': row['food_id'],
        'description': row['description'], 'source_url': row['source_url'],
        'acquisition': row.get('acquisition', data()['acquisition']),
        'original_values': row['original_values'], 'source': source}
    return NutritionEvidence(source=source, source_product_id=str(row['food_id']),
        nutrition=dict(values), nutrition_basis=row['description'] + '; generiskt referensvärde per 100 g, inte produktdeklaration.',
        field_sources={f'nutrition.{k}': (proof,) for k in values}, ingredient=canonical)
