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
NORDIC_PATH = PATH.with_name('matvaretabellen-20261121.json')
MACROS = {'kcal', 'protein_g', 'fat_g', 'carbs_g'}

# Owner request 2026-11-21: plain liquids sold by volume whose table is per
# 100 g (or missing/contradictory) use a food-specific density. A complete,
# consistent per-gram product table is converted; otherwise the generic SLV
# food is used. Flavoured, sweetened or mixed products stay unmapped.
_LIQUIDS = {
    'grädde': (r'vispgrädde(?: 40 ?%)?(?: (?:eko|ekologisk|svensk))*',
               {'ingredienser', 'högpastöriserad', 'pastöriserad', 'grädde', 'krav', 'ekologisk', 'råvara',
                'ursprung', 'sverige'}, {'': 1715}),
    'mjölk': (r'(lätt|mellan|standard)?mjölk(?: (?:eko|ekologisk|svensk|(\d+(?:[,.]\d+)?) ?%))*',
              {'ingredienser', 'lågpastöriserad', 'högpastöriserad', 'pastöriserad', 'mjölk', 'sverige', 'vitamin',
               'd', 'ekologisk', 'krav'}, {'lätt': 151, 'mellan': 150, 'standard': 123}),
    'sojasås': (r'(?:japansk )?sojasås(?: (?:eko|ekologisk|japansk|kikkoman|naturligt bryggd))*',
                {'ingredienser', 'vatten', 'sojabönor', 'vete', 'salt', 'ekologiska', 'ekologiskt', 'ekologisk'},
                {'': 909}),
    'ättiksprit 12 procent': (r'ättiksprit 12 ?%', {'ingredienser', 'vatten', 'ättiksyra', 'ättiksprit'}, {'': 1965}),
    'äppelcidervinäger': (r'äppelcider ?vinäger(?: (?:eko|ekologisk|ofiltrerad|naturell))*',
                          {'ingredienser', 'äppelcidervinäger', 'äppelcider', 'vinäger', 'ekologisk', 'ofiltrerad',
                           'surhetsgrad', 'syrahalt', 'ättiksyra'}, {'': 1967}),
    'olivolja': (r'(?:ekologisk |eko )?olivolja(?: (?:extra virgin|extra vergine|extra jungfru|jungfru|virgin|classico|'
                 r'eko|ekologisk|italiensk|spansk|grekisk|kalamata|arbequina|florens|tradición|unfiltered|'
                 r'koroneiki|picual))*',
                 {'ingredienser', 'olivolja', 'extra', 'jungfruolivolja', 'jungfru', 'jungfruolja', 'vergine', 'virgin',
                  'ekologisk', 'ursprung', 'spanien', 'italien', 'grekland', 'eu', 'kallextraherad', 'kallpressad',
                  'av', 'oliver', 'italienska', 'krav'}, {'': 4659}),
}

VOLUME_FALLBACK = frozenset({'citronjuice', *_LIQUIDS})


@lru_cache(maxsize=1)
def density_data():
    return json.loads(PATH.read_bytes())


@lru_cache(maxsize=1)
def nordic_density_data():
    return json.loads(NORDIC_PATH.read_bytes())


def _plain_liquid(canonical, label, composition, fact):
    """Generic or product per-100 g evidence for a plain liquid, else None."""
    pattern, allowed, references = _LIQUIDS[canonical]
    match = re.fullmatch(pattern, label)
    if not match:
        return None
    listed = re.sub(r'\([^()]*\)', ' ', composition.split('kan innehålla')[0])
    listed = re.split(r'\*+\s*krav|krav-ekologisk|\*\s*ekologisk ingrediens', listed)[0]
    words = set(re.findall(r'[a-zåäö]+', listed))
    if composition and not words <= allowed:
        return None
    if (fact and not fact.conflicts and fact.nutrition_unit == 'g' and fact.nutrition_preparation == 'as_sold'
            and MACROS <= fact.nutrition.keys()):
        return fact
    if fact and fact.nutrition and not fact.conflicts and MACROS <= fact.nutrition.keys():
        return None  # A complete table on another basis is the caller's to use.
    key = (match.group(1) if match.groups() else '') or ''
    if canonical == 'mjölk':
        # Plain "Mjölk 3%" is standard milk; other unnamed fat levels stay unmapped.
        fat = (match.group(2) or '').replace(',', '.')
        key = key or ({'3': 'standard', '3.0': 'standard', '': 'standard'}.get(fat, ''))
        if fat and key != 'standard' and {'lätt': '0.5', 'mellan': '1.5'}.get(key) not in {fat, None}:
            return None
    identity = references.get(key)
    return reference_evidence(identity) if identity else None


def volume_evidence(product, name, fact):
    canonical = canonicalize_ingredient_name(name)
    label = ' '.join(product.name.casefold().split())
    composition = ' '.join(fact.ingredients).casefold() if fact else ''
    if canonical == 'citronjuice':
        from app.services.complete_recipes import plain_juice_composition

        # Fresh-juice density is only a proxy for essentially pure pressed juice.
        # Never apply it to concentrate, sweetened drinks or diluted mixtures.
        if (not re.fullmatch(r'citronjuice(?: eko| ekologisk)*', label)
                or 'koncentrat' in composition or not plain_juice_composition(canonical, composition)):
            return None
        if fact and not fact.conflicts and fact.nutrition_unit == 'g' and MACROS <= fact.nutrition.keys():
            evidence = fact
        elif fact and (fact.conflicts or not fact.nutrition):
            # Owner request 2026-11-21: a pure lemon juice whose own table is
            # missing or contradictory uses Livsmedelsverket's fresh lemon juice
            # (generic reference, never relabelled as the product's table).
            evidence = reference_evidence(645)
        else:
            return None
    elif canonical in _LIQUIDS:
        evidence = _plain_liquid(canonical, label, composition, fact)
        if evidence is None:
            return None
    elif fact and fact.conflicts:
        return None
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
    return density_converted(evidence, canonical)


def density_converted(evidence, canonical):
    """Per-100 g evidence as per-100 ml with the reviewed density for this food."""
    if evidence.nutrition_preparation != 'as_sold':
        return None
    if canonical in density_data()['density']:
        data, label = density_data(), 'DTU'
        row, source, acquisition = data['density'][canonical], data['source'], data['density'][canonical]['acquisition']
    elif canonical in nordic_density_data()['density']:
        data, label = nordic_density_data(), 'Matvaretabellen (vikt per dl)'
        row, source, acquisition = data['density'][canonical], data['attribution'], data['acquisition']
    else:
        return None
    if row['unit'] != 'g/ml' or not 0 < row['value'] < 2:
        raise ValueError('Invalid reviewed density')
    transformation = {
        'kind': 'food_specific_density_estimate', 'source': source,
        'source_url': row['source_url'], 'acquisition': acquisition,
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
        nutrition_basis=evidence.nutrition_basis + f'; uppskattat per 100 ml med livsmedelsspecifik referensdensitet från {label}.',
        field_sources={k: (*v, transformation) for k, v in evidence.field_sources.items() if k.startswith('nutrition.')})
