"""Only a known inherited default may yield to explicit dinner distribution.

Category (one per recipe), culinary primary (one profile label), authored main
proteins (all substantive primary inputs) and base IDs remain distinct gates.
Capacity uses actual profile labels and distinct bases, never product prices.
"""
from collections import defaultdict
from dataclasses import replace

from app.services.personal_policy import PolicyConflict, protein_category
from app.services.recipe_week_variation import main_protein_sources


def resolve_current_variation(request, policy, constraints, recipes):
    intent = request.variation_intent
    if intent is None:
        return policy, constraints, None
    origins = dict(intent.field_origins)
    key = 'max_same_primary_ingredient_meals'
    if key in (request.recipe_diversity_overrides or {}) and origins.get(key) == 'default':
        origins[key] = 'explicit'
    original = policy.max_same_primary_ingredient_meals
    effective = original
    evidence = []
    for meal in request.personal.meals:
        if meal.meal_type != 'dinner':
            continue
        for category, required in meal.distribution.items():
            if not required:
                continue
            eligible = [r for r in recipes if protein_category(r) == category]
            if not eligible:
                continue
            common_sources = set.intersection(*(set(main_protein_sources(r)) for r in eligible))
            protein_cap = request.recipe_preferences.max_same_main_protein_dinners
            if protein_cap is not None and common_sources and required > protein_cap:
                raise PolicyConflict(f"Fördelningen kräver {required} {category}, men högst {protein_cap} middagar per huvudprotein tillåts. Alla aktuellt kvalificerade alternativ delar {', '.join(sorted(common_sources))}.", code='RECIPE_CHOICES_CONFLICT')
            if effective is None:
                continue
            domains = defaultdict(set)
            for recipe in eligible:
                primary = constraints.primary_ingredients.get(recipe.name)
                if not primary:
                    break  # Unknown classification cannot prove capacity.
                domains[primary].add(recipe.design.base_id)
            else:
                def capacity(cap, domains=domains):
                    return sum(min(cap, len(bases)) for bases in domains.values())
                if capacity(effective) >= required or capacity(7) < required:
                    continue
                origin = origins.get(key, 'unknown')
                row = {'category':category, 'required':required, 'primary_labels':sorted(domains),
                       'capacity_before':capacity(effective), 'scope':'current qualified recipe pool'}
                if origin != 'default':
                    raise PolicyConflict(f"Fördelningen kräver {required} {category}, men gränsen {effective} för samma huvudråvara ger kapacitet {capacity(effective)} bland aktuellt kvalificerade recept. Gränsens ursprung är {origin}; ändra ett av valen uttryckligen.",
                        code='RECIPE_CHOICES_CONFLICT', diagnostics={'variation_conflict':row, 'field_origins':origins})
                effective = next(cap for cap in range(effective+1, 8) if capacity(cap) >= required)
                evidence.append(row)
    if effective != original:
        policy = policy.model_copy(update={key:effective})
        constraints = replace(constraints, **{key:effective})
    return policy, constraints, {'version':intent.version, 'field_origins':origins,
        'original_primary_limit':original, 'effective_primary_limit':effective, 'adjustments':evidence,
        'message': (f"Standardgränsen för samma huvudråvara har anpassats från {original} till {effective} för din valda måltidsfördelning. Övriga gränser behålls." if evidence
                    else 'Dina egna variationsgränser och tidigare okända fältursprung behålls.')}
