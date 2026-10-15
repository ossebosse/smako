"""Opt-in nutrition conversion using a reviewed food-specific density.

Never changes purchased package quantities, prices or product declarations.
The caller must require nutrition-estimate consent and validate recipe form.
"""
import json
import re
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.nutrition_reference import NutritionEvidence, reference_evidence

PATH = Path(__file__).parents[1] / 'data/nutrition/dtu-density-20261015.json'
MACROS = {'kcal', 'protein_g', 'fat_g', 'carbs_g'}


@lru_cache(maxsize=1)
def density_data():
    return json.loads(PATH.read_bytes())


def volume_evidence(product, name, fact):
    if fact and fact.conflicts:
        return None
    canonical = canonicalize_ingredient_name(name)
    label = ' '.join(product.name.casefold().split())
    composition = ' '.join(fact.ingredients).casefold() if fact else ''
    if canonical == 'citronjuice':
        from app.services.complete_recipes import plain_juice_composition

        # Fresh-juice density is only a proxy for essentially pure pressed juice.
        # Never apply it to concentrate, sweetened drinks or diluted mixtures.
        if (not re.fullmatch(r'citronjuice(?: eko| ekologisk)*', label)
                or 'koncentrat' in composition or not plain_juice_composition(canonical, composition)
                or not fact or fact.nutrition_unit != 'g' or not MACROS <= fact.nutrition.keys()):
            return None
        evidence = fact
    elif canonical == 'rapsolja':
        if not re.fullmatch(r'rapsolja(?: kallpressad| eko| ekologisk| d-vitaminberikad)*', label):
            return None
        if composition and re.search(r'olivolja|solrosolja|smör|vatten|arom', composition):
            return None
        if fact and fact.nutrition:
            if fact.nutrition_unit != 'g' or not MACROS <= fact.nutrition.keys():
                return None
            evidence = fact
        else:
            evidence = reference_evidence(2189)
    else:
        return None
    if evidence.nutrition_preparation != 'as_sold':
        return None
    row = density_data()['density'][canonical]
    if row['unit'] != 'g/ml' or not 0 < row['value'] < 2:
        raise ValueError('Invalid reviewed density')
    transformation = {
        'kind': 'food_specific_density_estimate', 'source': density_data()['source'],
        'source_url': row['source_url'], 'acquisition': row['acquisition'],
        'food_id': row['food_id'], 'description': row['description'],
        'density_g_per_ml': row['value'], 'original_nutrition': dict(evidence.nutrition),
        'operation': 'source_per_100_g * reference_density_g_per_ml',
        'purchase_quantity_changed': False,
    }
    if not isinstance(evidence, NutritionEvidence):
        evidence = NutritionEvidence(source=evidence.source, source_product_id=evidence.source_product_id,
            nutrition=evidence.nutrition, nutrition_basis=evidence.nutrition_basis,
            field_sources=evidence.field_sources)
    return replace(evidence, nutrition={k: v * row['value'] for k, v in evidence.nutrition.items()},
        nutrition_unit='ml', evidence_kind='food_specific_density_estimate',
        nutrition_basis=evidence.nutrition_basis + '; uppskattat per 100 ml med livsmedelsspecifik referensdensitet från DTU.',
        field_sources={k: (*v, transformation) for k, v in evidence.field_sources.items() if k.startswith('nutrition.')})
