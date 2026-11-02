"""Served-weight estimates only for reviewed, supported preparation methods."""
import math

from app.services.ingredient_normalizer import canonicalize_ingredient_name as canonical


def estimate_portion_weight(recipe, selected_by_name):
    from app.services.recipe_preparation import has_unmeasured_process

    if has_unmeasured_process(recipe):
        return None
    from app.services.personal_nutrition import (
        is_raw_salad_preparation,
        is_reference_preparation,
        reference_method,
    )
    from app.services.reviewed_cold_meals import preparation as cold_preparation

    cold = cold_preparation(recipe) or is_raw_salad_preparation(recipe)
    if recipe.design and recipe.design.method in {'cold_assembly', 'refrigerated_assembly'}:
        from app.services.recipe_library import validate_recipe_design
        validate_recipe_design(recipe)
        cold = True
    if cold and all(i.unit == 'g' for i in recipe.ingredients):
        # These exact instructions serve all weighed edible inputs, without
        # heating, added water or further draining. Dry oats absorb yogurt;
        # neither the absorption nor chopping creates additional served mass.
        return {'source': 'Smako: granskat recept, alla uppvägda ätbara ingredienser serveras',
            'method': 'reviewed_no_loss_cold_assembly', 'servings': recipe.servings,
            'total_g': sum(i.quantity for i in recipe.ingredients),
            'evidence_kind': 'served_weight_estimate',
            'basis': 'Uppskattad serverad vikt efter kall beredning; ingen uppmätt slutvikt.',
            'inputs': [{'ingredient': i.name, 'edible_g': i.quantity} for i in recipe.ingredients]}
    if not is_reference_preparation(recipe):
        return None
    # Soup/stew instructions add unspecified serving water. Never infer it.
    from app.services.personal_nutrition import reference_instructions
    if recipe.instructions in [reference_instructions('soup'), reference_instructions('stew')]:
        return None
    from app.services.nutrition_reference import COOKED, FRIED, product_reference, reference_data
    data = reference_data()
    terms = []
    for item in recipe.ingredients:
        selected = selected_by_name.get(canonical(item.name))
        if not selected:
            return None
        product, fact = selected
        identity = product_reference(product, item.name, fact)
        method = reference_method(recipe, item.name)
        prepared_id = (FRIED if method == 'fry' else COOKED).get(identity)
        if prepared_id is None:
            return None
        entry = data['preparations'][str(prepared_id)]
        main = [i for i in entry['ingredients'] if i['nummer'] == identity]
        if len(main) != 1 or any(i['nummer'] not in {identity, 1975} for i in entry['ingredients']):
            return None
        before = main[0]['viktForeTillagning']
        # The reference batch may contain added salt. These exact recipes do
        # not: only the named food's final mass belongs in the weight estimate.
        after = main[0]['viktEfterTillagning']
        if not all(isinstance(x, (float, int)) and math.isfinite(x) and x > 0 for x in (before, after)):
            return None
        terms.append({'ingredient': item.name, 'edible_input_g': item.quantity,
            'estimated_served_g': item.quantity * after / before,
            'raw_food_id': identity, 'prepared_food_id': prepared_id,
            'documented_raw_g': before, 'documented_food_after_g': after,
            'source_url': entry['source_url'], 'method': method})
    return {'source': 'Livsmedelsverket: dokumenterade råvaru- och tillagningsvikter',
        'method': 'food_specific_documented_batch_yield', 'servings': recipe.servings,
        'total_g': sum(t['estimated_served_g'] for t in terms),
        'evidence_kind': 'served_weight_estimate', 'inputs': terms,
        'basis': 'Uppskattad tillagad vikt med livsmedelsspecifikt utbyte; faktisk vikt kan avvika.'}
