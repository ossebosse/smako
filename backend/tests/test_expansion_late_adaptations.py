"""Final culinary alternatives retain batch, source, waiting and loss boundaries."""
import json
from pathlib import Path

import pytest
from app.models.personal import MealSettings
from app.models.recipe import RecipeDesign, RecipeStep
from app.models.recipe_preferences import RecipePreferences
from app.services.diet_policy import ingredient_is_excluded
from app.services.meal_library_content import identity, load_entries, manifest_entries
from app.services.recipe_library import (
    _scaled,
    current_recipes,
    matches_meal,
    validate_recipe_design,
)

REPORT = Path('docs/reviews/recipe-unblock-round2-20261101')


def test_vada_bread_version_keeps_batter_and_explicit_unknown_frying_loss():
    recipes=[r for r in current_recipes() if r.design.base_id=='smako-indian-vada-pav']
    assert len(recipes)==1 and recipes[0].design.variant_id=='simple'
    recipe=recipes[0]
    names={i.canonical_name:i for i in recipe.ingredients}
    assert 'pavbröd' not in names and names['mjukt hamburgerbröd'].quantity==416
    assert names['rapsolja'].quantity==220 and names['potatis'].quantity==750
    assert {p.operation for p in recipe.design.unmeasured_processes}=={'drain_after_cooking','deep_fry_and_drain'}
    doubled=_scaled(recipe,8)
    validate_recipe_design(doubled)
    text=' '.join(doubled.instructions)
    assert '2400 ml vatten' in text and '320 ml vatten' in text and '40 ml vatten' in text
    assert 'kvarvarande smet' in text and 'två vada per portion' in text


def test_cornflakes_chivda_uses_ready_to_eat_flakes_and_preserves_extended_variation():
    recipes = [r for r in current_recipes() if r.design.base_id == 'smako-indian-chivda']
    assert len(recipes) == 2
    for recipe in recipes:
        names = {i.canonical_name: i for i in recipe.ingredients}
        assert names['cornflakes'].form == 'as_sold' and names['cornflakes'].quantity == 35
        assert names['rostade jordnötter'].quantity == 15 and 'risflingor' not in names
        assert 'Cornflakes-chivda' in recipe.name and not recipe.design.unmeasured_processes
        assert {'russin','kokosflingor','senapsfrön'} <= names.keys() if recipe.design.variant_id == 'extended' else 'russin' not in names
        text = ' '.join(recipe.instructions)
        assert 'häll inte bort någon olja' in text and 'rostade osaltade' in text
        assert recipe.design.steps[-2].duration_minutes == 10
        doubled = _scaled(recipe,2)
        validate_recipe_design(doubled)
        assert next(i.quantity for i in doubled.ingredients if i.canonical_name == 'cornflakes') == 70


def test_khua_kling_separates_dried_leaf_infusion_whole_stalk_and_counted_eggs():
    recipes = [r for r in current_recipes() if r.design.base_id == 'smako-thai-khua-kling']
    assert len(recipes) == 3
    for recipe in recipes:
        names = {i.canonical_name:i for i in recipe.ingredients}
        assert names['röd currypasta'].quantity == 55 and 'sydthailändsk currypasta' not in names
        assert names['torkade makrutlimeblad'].quantity == 1 and names['citrongräs'].quantity == 40
        assert names['citrongräs'].form == 'as_sold'
        assert 'kokta ägg' not in names and 'rapsolja' not in names
        if recipe.design.variant_id != 'simple':
            assert names['ägg'].unit == 'st' and names['ägg'].quantity == 4
            assert any(p.operation=='peel_after_cooking' for p in recipe.design.unmeasured_processes)
        doubled = _scaled(recipe,8)
        validate_recipe_design(doubled)
        text = ' '.join(doubled.instructions)
        assert text.count('200 ml vatten') == 2 and '1120 ml vatten' in text
        assert '72 °C' in text and 'Behåll allt köttfett' in text


def test_papadzules_coriander_and_corn_tortillas_have_explicit_egg_and_thaw_method():
    recipes = [r for r in current_recipes() if r.design.base_id == 'smako-mexican-papadzules']
    assert len(recipes) == 3
    for recipe in recipes:
        names = {i.canonical_name:i for i in recipe.ingredients}
        assert names['koriander'].quantity == 20 and 'epazote' not in names
        assert names['majstortillas'].quantity == 400 and 'masa harina' not in names
        assert names['ägg'].unit == 'st' and names['ägg'].quantity == 8
        process, = recipe.design.unmeasured_processes
        step = next(s for s in recipe.design.steps if s.id == process.step_id)
        assert 'Skala, kasta skalen' in step.text
        doubled = _scaled(recipe,8)
        validate_recipe_design(doubled)
        text=' '.join(doubled.instructions)
        assert '3200 ml vatten' in text and '1100 ml vatten' in text
        assert 'fyra tallrikar' not in text and 'hela pumpakärnssåsen' in text
        if recipe.design.variant_id=='extended':
            assert recipe.design.steps[1].duration_minutes == 120 and 'avokado' in text


def test_arroz_coriander_siblings_retain_seafood_broth_and_heat_frozen_herbs():
    recipes=[r for r in current_recipes() if r.design.base_id=='smako-mexican-arroz-tumbada'
             and r.design.variant_id!='simple']
    assert len(recipes)==2
    for recipe in recipes:
        names={i.canonical_name:i for i in recipe.ingredients}
        assert 'epazote' not in names and names['koriander'].quantity==15
        assert names['blåmusselkött utan skal'].quantity==200
        text=' '.join(recipe.instructions)
        assert 'hela den uppvägda frysta koriandern' in text and 'Allt spad behålls' in text
        assert recipe.design.steps[1].duration_minutes==720
        doubled=_scaled(recipe,8)
        validate_recipe_design(doubled)
        assert '2800 ml vatten' in ' '.join(doubled.instructions)


def test_polsa_uses_named_beef_and_gross_liver_with_unknown_trim_and_broths():
    recipes = [r for r in current_recipes() if r.design.base_id == 'smako-swedish-polsa']
    assert len(recipes) == 3
    for recipe in recipes:
        names = {i.canonical_name: i for i in recipe.ingredients}
        assert 'nöthjärta' not in names and 'fläsklever' not in names
        assert names['högrev'].quantity == 500
        assert names['ungnötslever'].quantity == 250 and names['ungnötslever'].form == 'as_sold'
        assert any(p.operation == 'trim_before_cooking' and p.ingredient_keys == ('ungnötslever|as_sold',)
                   for p in recipe.design.unmeasured_processes)
        assert sum(p.operation == 'drain_after_cooking' for p in recipe.design.unmeasured_processes) == 3
        doubled = _scaled(recipe,8)
        validate_recipe_design(doubled)
        text = ' '.join(doubled.instructions)
        assert '3400 ml vatten' in text and '1800 ml vatten från köttkoket' in text
        assert 'högst 200 ml vatten' in text and 'hela den korta rödbetslagen' in text
        if recipe.design.variant_id == 'extended':
            assert 'väg den råa ätliga mängden utan skal' in text and 'Servera allt äggsmör' in text


def test_pindi_chole_retains_tea_method_and_scales_new_lemon_and_separate_bread_water():
    recipes = [r for r in current_recipes() if r.design.base_id == 'smako-indian-pindi-chole']
    assert len(recipes) == 3
    for recipe in recipes:
        names = {i.canonical_name: i for i in recipe.ingredients}
        assert 'cholemasala' not in names and 'amchur' not in names
        assert {'malen koriander','garam masala','spiskummin','gurkmeja','paprikapulver','cayennepeppar'} <= names.keys()
        assert names['kikärtor'].form == 'dry' and names['svart te'].quantity == 5
        assert {p.operation for p in recipe.design.unmeasured_processes} == {
            'drain_before_cooking','remove_after_infusion','drain_after_cooking'}
        doubled = _scaled(recipe,8)
        validate_recipe_design(doubled)
        text = ' '.join(doubled.instructions)
        assert '290 ml vatten' in text and '240 ml vatten' in text and '2400 ml vatten (kallt)' in text
        assert 'över fyra portioner' not in text and 'alla teblad' in text
        assert names['citronjuice'].quantity == (55 if recipe.design.variant_id == 'extended' else 30)


def test_curry_leaf_free_chicken_keeps_variant_differences_and_cold_thaw_and_oil_losses():
    recipes = [r for r in current_recipes() if r.design.base_id == 'smako-indian-chicken-65-pannstekt']
    assert len(recipes) == 3
    for recipe in recipes:
        names = {i.canonical_name: i for i in recipe.ingredients}
        assert 'curryblad' not in names and 'kashmirichilipulver' not in names
        assert names['paprikapulver'].quantity == 3 and names['cayennepeppar'].quantity == .3
        assert 'utan curryblad' in recipe.name
        operations = {p.operation for p in recipe.design.unmeasured_processes}
        assert operations == {'drain_before_cooking', 'deep_fry_and_drain'}
        doubled = _scaled(recipe, 8)
        validate_recipe_design(doubled)
        text = ' '.join(doubled.instructions)
        assert '1120 ml vatten' in text and '74 °C' in text and '24 timmars kylupptining' in text
        if recipe.design.variant_id != 'simple':
            assert {'vitlök','ingefära','citronjuice'} <= names.keys()
        if recipe.design.variant_id == 'extended':
            assert {'rismjöl','gurka','mynta','spiskummin'} <= names.keys()
            assert names['mynta'].product_requirements == ('pack:intake_all_shape_trimmed_mint',)


def test_dried_lime_leaf_wok_strains_leaves_and_preserves_water_and_dose_scaling():
    recipes = [r for r in current_recipes() if r.design.base_id == 'smako-thai-pad-prik-king-tofu']
    assert len(recipes) == 3
    for recipe in recipes:
        names = {i.canonical_name: i for i in recipe.ingredients}
        assert 'makrutlimeblad' not in names
        assert names['torkade makrutlimeblad'].form == 'dry'
        assert names['torkade makrutlimeblad'].quantity == 1
        assert any(p.operation == 'remove_after_infusion' and
                   p.ingredient_keys == ('torkade makrutlimeblad|dry',)
                   for p in recipe.design.unmeasured_processes)
        doubled = _scaled(recipe, 8)
        validate_recipe_design(doubled)
        text = ' '.join(doubled.instructions)
        assert text.count('200 ml vatten') == 2 and '1120 ml vatten' in text
        assert 'Ta bort alla blad och hårda fragment' in text
        assert 'ingen bönvätska hälls bort' in text and 'all kryddpasta och stekolja' in text


def test_nogada_peppers_are_weighed_after_coring_before_roasting_and_extra_filling_is_served():
    recipes = [r for r in current_recipes() if r.design.base_id == 'smako-mexican-chiles-en-nogada']
    assert len(recipes) == 3
    for recipe in recipes:
        names = {i.canonical_name: i for i in recipe.ingredients}
        assert 'poblano' not in names and names['paprika'].quantity == 700
        assert 'Paprika en nogada' in recipe.name
        assert any(p.operation == 'peel_after_cooking' and p.ingredient_keys == ('paprika|raw_edible',)
                   for p in recipe.design.unmeasured_processes)
        doubled = _scaled(recipe, 8)
        validate_recipe_design(doubled)
        text = ' '.join(doubled.instructions)
        assert '60 ml vatten' in text and 'mellan fyra tallrikar' not in text
        assert 'väg halvorna före rostning' in text and 'inte ryms bredvid halvorna' in text
        assert 'granatäppelkärnor med all tiningssaft' in text


def test_one_pot_pasta_uses_short_shape_and_keeps_starch_water_and_hot_herbs():
    recipes = [r for r in current_recipes() if r.design.base_id == 'smako-italian-pasta-patate-provola']
    assert len(recipes) == 3
    for recipe in recipes:
        names = {i.canonical_name: i for i in recipe.ingredients}
        assert 'rökt provola' not in names
        assert names['mozzarella'].form == 'preserved_drained' and names['mozzarella'].quantity == 200
        assert names['pasta'].product_requirements == ('pack:pasta',)
        doubled = _scaled(recipe, 8)
        validate_recipe_design(doubled)
        text = ' '.join(doubled.instructions)
        assert '2000 ml vatten' in text and '400 ml vatten' in text
        assert 'Behåll all grytsås' in text and 'utan rökt ost' in recipe.name
        if recipe.design.variant_id != 'simple':
            assert 'minst tre minuter före koktidens slut' in text
            assert 'basilikan' not in next(s.text for s in recipe.design.steps if 'Ta av grytan' in s.text)


def test_lemongrass_fishcakes_keep_gross_trim_and_unknown_frying_and_thaw_losses():
    recipes = [r for r in current_recipes() if r.design.base_id == 'smako-thai-tod-man-pla']
    assert len(recipes) == 3
    for recipe in recipes:
        names = {i.canonical_name: i for i in recipe.ingredients}
        assert 'makrutlimeblad' not in names
        assert names['citrongräs'].form == 'as_sold' and names['citrongräs'].quantity == 12
        assert names['citrongräs'].product_requirements == ('pack:intake_all_shape_top5_whole_lemongrass',)
        operations = {p.operation for p in recipe.design.unmeasured_processes}
        assert operations == {'trim_before_cooking', 'drain_before_cooking', 'deep_fry_and_drain'}
        doubled = _scaled(recipe, 8)
        validate_recipe_design(doubled)
        text = ' '.join(doubled.instructions)
        assert 'fyra tunna kakor per portion' in text and 'sexton' not in text
        assert '100 ml vatten' in text and 'minst 72 °C' in text
        if recipe.design.variant_id == 'extended':
            assert 'rostade jordnötter' in names and 'jordnötter' not in names


def test_feta_alternative_changes_browning_method_and_cooks_frozen_parsley():
    recipes = [r for r in current_recipes() if r.design.base_id == 'smako-greek-tsouxti-mani']
    assert len(recipes) == 3
    for recipe in recipes:
        names = {i.canonical_name: i.quantity for i in recipe.ingredients}
        assert names['fetaost'] == 100 and 'myzithra' not in names
        text = ' '.join(recipe.instructions)
        assert 'Fetan ska inte stekas i detta steg' in text
        assert 'minst 72 °C' in text
        doubled = _scaled(recipe, 8)
        validate_recipe_design(doubled)
        scaled_text = ' '.join(doubled.instructions)
        assert '5000 ml vatten' in scaled_text and '160 ml vatten från pastakoket' in scaled_text
        assert 'mellan fyra portioner' not in scaled_text
        if recipe.design.variant_id == 'extended':
            assert 'fryst hackad persilja' in text and 'minst tre minuter' in text
            assert 'hackad persilja' not in recipe.instructions[0]


def test_muscovado_crepes_scale_both_water_doses_and_preserve_distinct_variants():
    recipes = [r for r in current_recipes() if r.design.base_id == 'smako-indian-patishapta']
    assert len(recipes) == 2
    for recipe in recipes:
        doubled = _scaled(recipe, 2)
        validate_recipe_design(doubled)
        names = {i.canonical_name: i.quantity for i in doubled.ingredients}
        assert names['mörkt muscovadosocker'] == 20 and 'jaggery' not in names
        assert 'muscovado' in recipe.name and 'jaggery' not in recipe.design.side
        text = ' '.join(doubled.instructions)
        assert 'två tunna pannkakor per portion' in text
        if recipe.design.variant_id == 'simple':
            assert '160 ml vatten' in text and '100 ml vatten' in text
            assert not {'mjölk', 'mannagryn', 'kardemumma'} & names.keys()
        else:
            assert '80 ml vatten' in text and 'malen kardemumma' in text
            assert {'mjölk', 'mannagryn', 'kardemumma'} <= names.keys()


def test_blocked_steamed_rice_version_is_preserved_but_cannot_enter_a_menu():
    manifest = manifest_entries()
    assert not any(r.design.base_id == 'smako-thai-khao-tom-mat' for r in current_recipes())
    recipes = [r for r in load_entries(manifest['current'] + manifest['history'])
               if r.design.base_id == 'smako-thai-khao-tom-mat']
    assert len(recipes) == 1 and recipes[0].design.variant_id == 'simple'
    recipe = recipes[0]
    assert 'bakpapperspaket' in recipe.name
    assert not any(i.canonical_name == 'bananblad' for i in recipe.ingredients)
    assert 'livsmedelsgodkänt bakplåtspapper' in recipe.design.equipment
    process, = recipe.design.unmeasured_processes
    assert process.operation == 'drain_before_cooking' and process.ingredient_keys == ('klibbigt ris|dry',)
    doubled = _scaled(recipe, 2)
    assert identity(recipe) in manifest['revocations']
    with pytest.raises(ValueError, match='återkallats'):
        validate_recipe_design(doubled)
    text = ' '.join(doubled.instructions)
    assert '360 ml vatten' in text and '600 ml vatten (hett)' in text
    assert 'två små paket per portion' in text
    proof = json.loads((REPORT / 'qualification-stage34.json').read_bytes())
    blocked, = proof['modes']['estimated']['recipes']
    assert blocked['id'] == identity(recipe) and blocked['status'] == 'data_blocked'
    assert any(b['identity'] == 'klibbigt ris|dry' for b in blocked['input_blocks'])


def test_mozzarella_pasta_keeps_drained_basis_and_distinct_baked_filling():
    recipes = [r for r in current_recipes() if r.design.base_id == 'smako-italian-pasta-ncasciata']
    assert len(recipes) == 3
    for recipe in recipes:
        names = {i.canonical_name: i for i in recipe.ingredients}
        assert 'caciocavallo' not in names
        assert names['mozzarella'].form == 'preserved_drained' and names['mozzarella'].quantity == 200
        assert names['pasta'].product_requirements == ('pack:pasta',) and recipe.design.version == '1.0.2'
        assert {'ägg', 'nötfärs', 'aubergine'} <= names.keys()
        assert any(p.operation == 'drain_after_cooking' for p in recipe.design.unmeasured_processes)
        doubled = _scaled(recipe, 8)
        validate_recipe_design(doubled)
        text = ' '.join(doubled.instructions)
        assert '800 ml vatten' in text and '4600 ml vatten' in text and 'Dela i fyra' not in text
        if recipe.design.variant_id != 'simple':
            assert 'fryst basilika varit genomhet minst tre minuter' in text
        if recipe.design.variant_id == 'extended':
            assert {'ärtor', 'ströbröd', 'parmesan'} <= names.keys()
    review = json.loads((REPORT / 'pasta-shape-corrections.json').read_bytes())
    proof = json.loads((REPORT / 'qualification-pasta-shape-corrections.json').read_bytes())
    assert len(review['recipes']) == 3 and proof['pack_sha256'] == review['pack_sha256']
    for row in proof['modes']['estimated']['recipes']:
        assert row['status'] == 'verified' and row['audit']['passed']
        items = [i for store in row['basket']['stores'] for i in store['items']
                 if i['ingredient'].startswith('pasta [')]
        assert len(items) == 1 and 'spaghetti' not in items[0]['product_name'].lower()


def test_cheese_alternatives_preserve_unknown_losses_and_scale_actual_water():
    for recipe in current_recipes():
        base = recipe.design.base_id
        if base not in {'smako-italian-pasta-alla-norma', 'smako-greek-pitarakia-milos'}:
            continue
        assert recipe.preparation.version == 'smako-authored-losses-v3'
        operations = {p.operation for p in recipe.design.unmeasured_processes}
        assert 'trim_before_cooking' in operations
        assert 'pecorino' in recipe.name.lower()
        doubled = _scaled(recipe, recipe.servings * 2)
        validate_recipe_design(doubled)
        text = ' '.join(doubled.instructions)
        if base.endswith('pasta-alla-norma'):
            assert 'drain_after_cooking' in operations
            assert recipe.design.version == '1.0.2'
            assert '300 ml vatten från pastakoket' in text
            assert '100 ml vatten från pastakoket' in text
            assert 'minst tre minuter' in text
        else:
            assert 'deep_fry_and_drain' in operations
            assert '44 ml vatten' in text and '6 ml vatten' in text
            assert '170 °C' in text and 'fyra rundlar' not in text


def test_pepper_versions_keep_roasted_skin_loss_and_frozen_herbs_out_of_raw_salad():
    recipes = [r for r in current_recipes() if r.design.base_id == 'smako-mexican-rajas-con-crema']
    assert len(recipes) == 3
    for recipe in recipes:
        inputs = {i.canonical_name: i for i in recipe.ingredients}
        assert 'poblano' not in inputs and 'masa harina' not in inputs
        assert inputs['majstortillas'].quantity == 400 and inputs['jalapeño'].quantity == 6
        assert recipe.preparation.version == 'smako-authored-losses-v3'
        process, = recipe.design.unmeasured_processes
        step = next(s for s in recipe.design.steps if s.id == process.step_id)
        assert process.operation == 'peel_after_cooking' and 'Dra av löst mörkt skinn' in step.text
        if recipe.design.variant_id != 'simple':
            assert inputs['mozzarella'].form == 'preserved_drained'
        if recipe.design.variant_id == 'extended':
            text = ' '.join(recipe.instructions)
            assert 'koriandern ska sjuda i gräddsåsen' in text
            assert 'hacka koriander och vänd' not in text


def test_lamb_successors_change_only_the_reviewed_cut_and_gross_basis_and_keep_history():
    manifest = manifest_entries()
    issued = {identity(r): r for r in load_entries(manifest['current'] + manifest['history'])}
    current = {identity(r): r for r in current_recipes()}
    review = json.loads((REPORT / 'lamb-corrections.json').read_bytes())
    proof = json.loads((REPORT / 'qualification-lamb-corrections.json').read_bytes())
    assert len(review['recipes']) == 9
    assert proof['pack_sha256'] == review['pack_sha256'] and not proof['input_only']
    assert {r['id'] for r in proof['modes']['estimated']['recipes']} == {r['runtime_id'] for r in review['recipes']}
    assert all(r['status'] == 'verified' and r['audit']['passed'] for r in proof['modes']['estimated']['recipes'])
    for row in review['recipes']:
        before, after = issued[row['previous_id']], current[row['runtime_id']]
        assert before.design.content_sha256 == row['previous_content_sha256']
        assert after.design.content_sha256 == row['content_sha256']
        assert row['previous_id'] in manifest['revocations'] and row['previous_id'] not in current
        old = {i.canonical_name: i for i in before.ingredients}
        new = {i.canonical_name: i for i in after.ingredients}
        lamb, leg = old.pop('lammkött'), new.pop('benfri lammstek')
        assert old == new
        assert lamb.quantity == leg.quantity and lamb.unit == leg.unit == 'g'
        assert lamb.form == 'raw_edible' and leg.form == 'as_sold'
        assert lamb.product_requirements != leg.product_requirements
        assert after.preparation.version == 'smako-authored-losses-v3'
        assert any(p.operation == 'trim_before_cooking' and p.step_id == 's3' for p in after.design.unmeasured_processes)
        assert after.design.steps[1].duration_minutes == 1440
        assert 1440 < after.design.waiting_minutes < after.design.total_minutes <= 2880
        for portions in (1, 4, 8):
            scaled = _scaled(after, portions)
            validate_recipe_design(scaled)
            assert scaled.design.steps[1].duration_minutes == 1440
            assert '24 timmar' in scaled.instructions[1]
        assert ingredient_is_excluded('benfri lammstek', ['lammkött'])


def test_long_thaw_is_accepted_by_content_contract_but_not_short_user_time_limits():
    recipe = next(r for r in current_recipes() if r.design.base_id == 'smako-indian-rogan-josh')
    prefs = RecipePreferences(mode='complete', min_ingredients=3, max_ingredients=20)
    meal = MealSettings(count=1, servings=4, recipe_choices={'min_ingredients': 1, 'max_ingredients': 40})
    assert matches_meal(recipe, meal, prefs)
    limited = meal.model_copy(update={'recipe_choices': meal.recipe_choices.model_copy(update={'max_waiting_minutes': 1440})})
    assert not matches_meal(recipe, limited, prefs)
    RecipeDesign.model_validate(recipe.design.model_dump())
    with pytest.raises(ValueError):
        RecipeDesign.model_validate({**recipe.design.model_dump(), 'waiting_minutes': 2881})
    with pytest.raises(ValueError):
        RecipeStep.model_validate({**recipe.design.steps[1].model_dump(), 'duration_minutes': 1441})


def test_spinach_variants_retain_meaningful_spices_and_casing_loss_is_bound_to_removal():
    recipes = current_recipes()
    pies = {r.design.variant_id: r for r in recipes if r.design.base_id == 'smako-italian-torta-pasqualina'}
    simple = {i.canonical_name for i in pies['simple'].ingredients}
    standard = {i.canonical_name for i in pies['standard'].ingredients}
    extended = {i.canonical_name for i in pies['extended'].ingredients}
    assert {'mejram', 'muskot'} <= standard - simple
    assert {'tomat', 'basilika', 'rödvinsvinäger'} <= extended - standard
    assert 'mangold' not in standard | extended
    for variant in ('standard', 'extended'):
        assert '600' == f"{next(i.quantity for i in pies[variant].ingredients if i.canonical_name == 'spenat'):g}"
        assert any(p.operation == 'drain_after_cooking' for p in pies[variant].design.unmeasured_processes)
    for recipe in recipes:
        if recipe.design.base_id != 'smako-mexican-frijoles-puercos':
            continue
        process, = recipe.design.unmeasured_processes
        step = next(s for s in recipe.design.steps if s.id == process.step_id)
        assert process.ingredient_keys == ('färsk chorizokorv|as_sold',)
        assert 'kasta fjälstret' in step.text
        assert any('72 °C' in s.text for s in recipe.design.steps)


def test_selected_frozen_products_receive_reviewed_preparation_without_food_dose_changes():
    manifest = manifest_entries()
    issued = {identity(r): r for r in load_entries(manifest['current'] + manifest['history'])}
    current = {identity(r): r for r in current_recipes()}
    review = json.loads((REPORT / 'selected-product-corrections.json').read_bytes())
    proof = json.loads((REPORT / 'qualification-selected-product-corrections.json').read_bytes())
    assert len(review['recipes']) == 8 and proof['pack_sha256'] == review['pack_sha256']
    assert not proof['input_only']
    assert {r['id'] for r in proof['modes']['estimated']['recipes']} == {r['runtime_id'] for r in review['recipes']}
    assert all(r['status'] == 'verified' and r['audit']['passed'] for r in proof['modes']['estimated']['recipes'])
    for row in review['recipes']:
        old, new = issued[row['previous_id']], current[row['runtime_id']]
        assert old.design.content_sha256 == row['previous_content_sha256']
        assert new.design.content_sha256 == row['content_sha256']
        assert old.ingredients == new.ingredients
        assert row['previous_id'] in manifest['revocations'] and row['previous_id'] not in current
        text = ' '.join(new.instructions)
        if new.design.base_id.endswith('spaghetti-aglio-olio'):
            assert new.design.version == '1.0.3' and new.preparation.version == 'smako-authored-losses-v3'
            assert any(p.ingredient_keys == ('pasta|dry',) and p.operation == 'drain_after_cooking'
                       for p in new.design.unmeasured_processes)
            assert 'all uppvägd persilja. Sjud' in text
            assert 'minst tre minuter' in text
        elif new.design.base_id.endswith('sopa-de-lima'):
            assert new.design.steps[1].duration_minutes == 1440
            assert 'minst 74 °C' in text and 'all upptiningsvätska' in text
        else:
            assert 'Sjud vitlöken med 20 ml vatten' in text
            scaled = _scaled(new, 2)
            assert 'Sjud vitlöken med 40 ml vatten' in ' '.join(scaled.instructions)
