import json
from types import SimpleNamespace

import pytest
from app.models.personal import MealSettings, MealSlot
from app.models.recipe_preferences import RecipePreferences
from app.services import meal_library_content as content
from app.services import meal_prepared_artifacts as artifacts
from app.services.personal_planner import PersonalPlanner
from app.services.recipe_library import _registered


def pack(tmp_path):
    recipe=next(r for r in _registered() if r.design.content_source)
    raw=recipe.model_dump(mode='json')
    raw['design'].update(active_minutes=20,total_minutes=recipe.design.estimated_minutes,
                         meal_types=['breakfast'],base_id='smako-breakfast-independent-import-test')
    path=tmp_path/'input.json'
    path.write_bytes(content.encoded({'schema_version':content.SCHEMA,'pack_id':'independent-test','recipes':[raw]}))
    return path


def library_root(tmp_path):
    root=tmp_path/'library';root.mkdir()
    (root/content.MANIFEST.name).write_bytes(content.encoded({'schema_version':content.MANIFEST_SCHEMA,'current':[],'history':[]}))
    return root


def test_withdrawn_version_remains_readable_but_cannot_be_planned(monkeypatch):
    from app.services import recipe_library as library
    recipe = _registered()[0].model_copy(deep=True)
    key = content.identity(recipe)
    monkeypatch.setattr(content, "manifest_entries", lambda: {
        "current": [], "history": [], "revocations": {key: "Mängdbasis motsäger instruktionen"}})
    monkeypatch.setattr(content, "load_entries", lambda entries: (recipe,))
    library.reset_library_caches()
    try:
        assert not library.current_recipes()
        # Historical content is retained and still parses for immutable GETs.
        assert library._registered_history()[0].model_dump() == recipe.model_dump()
        with pytest.raises(ValueError, match="återkallats"):
            library.validate_recipe_design(recipe)
    finally:
        library.reset_library_caches()


def test_revocation_requires_known_version_and_preserves_all_content(tmp_path):
    path = pack(tmp_path);root = library_root(tmp_path)
    imported = content.import_pack(path, root=root)
    issued = (root / imported["published_file"]).read_bytes()
    before = (root / content.MANIFEST.name).read_bytes()
    with pytest.raises(ValueError, match="okänd"):
        content.revoke_recipe("unknown:1.0.0:base", "Wrong basis", root=root)
    assert before == (root / content.MANIFEST.name).read_bytes()
    key = imported["diff"][0]["id"]
    content.revoke_recipe(key, "Wrong basis", root=root)
    manifest = (root / content.MANIFEST.name).read_bytes()
    content.revoke_recipe(key, "Wrong basis", root=root)
    assert manifest == (root / content.MANIFEST.name).read_bytes()
    assert issued == (root / imported["published_file"]).read_bytes()


def test_import_idempotent_and_conflict_is_atomic(tmp_path):
    path=pack(tmp_path);root=library_root(tmp_path)
    first=content.import_pack(path,root=root)
    manifest=(root/content.MANIFEST.name).read_bytes()
    second=content.import_pack(path,root=root)
    assert first['published_file']==second['published_file'] and manifest==(root/content.MANIFEST.name).read_bytes()
    assert second['diff'][0]['status']=='unchanged'
    raw=json.loads(path.read_bytes());raw['recipes'][0]['name']+=' ändrad'
    path.write_bytes(content.encoded(raw))
    with pytest.raises(ValueError,match='Importkonflikt'):content.import_pack(path,root=root)
    assert manifest==(root/content.MANIFEST.name).read_bytes()


def test_invalid_post_is_reported_and_only_explicit_subset_published(tmp_path):
    path=pack(tmp_path);raw=json.loads(path.read_bytes());bad=json.loads(json.dumps(raw['recipes'][0]))
    bad['design']['base_id']='bad';bad['ingredients'][0]['canonical_name']='wrong'
    raw['recipes'].append(bad);path.write_bytes(content.encoded(raw))
    checked=content.validate_pack(path)
    assert len(checked['recipes'])==1 and len(checked['rejections'])==1
    assert checked['rejections'][0]['file']==str(path) and 'ingredients[0]' in checked['rejections'][0]['reason']
    root=library_root(tmp_path)
    with pytest.raises(ValueError,match='delmängd'):content.import_pack(path,root=root)
    result=content.import_pack(path,root=root,accepted_ids=[content.identity(checked['recipes'][0])])
    assert result['rejections'] and len(content.load_entries(content.manifest_entries(root)['current'],root))==1


def test_manifest_escape_duplicate_json_and_unknown_field(tmp_path):
    with pytest.raises(ValueError):content.checked_path(tmp_path,'../escape.json')
    path=tmp_path/'duplicate.json';path.write_text('{"recipes":[],"recipes":[]}',encoding='utf8')
    with pytest.raises(ValueError,match='Dubblerat'):content.read_json(path)
    path=pack(tmp_path);raw=json.loads(path.read_bytes());raw['recipes'][0]['executable']='evil.py';path.write_bytes(content.encoded(raw))
    assert 'executable' in content.validate_pack(path)['rejections'][0]['reason']


def test_existing_bake_method_imports_but_unknown_method_is_rejected(tmp_path):
    path=pack(tmp_path);raw=json.loads(path.read_bytes())
    raw['recipes'][0]['design']['method']='bake'
    path.write_bytes(content.encoded(raw))
    assert not content.validate_pack(path)['rejections']
    raw['recipes'][0]['design']['method']='unknown-executable-method'
    path.write_bytes(content.encoded(raw))
    assert content.validate_pack(path)['rejections']


def test_corrupt_artifact_recomputed_and_versions_negative_results_change(tmp_path,monkeypatch):
    monkeypatch.setenv('RECIPE_PREPARATION_CACHE_ROOT',str(tmp_path))
    calls=[]
    def compute():calls.append(1);return {'no_candidates':['egg']}
    assert artifacts.prepared('declarations',['inventory-v1'],compute)==compute()
    assert len(calls)==2
    artifacts.prepared('declarations',['inventory-v1'],compute)
    assert len(calls)==2
    next((tmp_path/'declarations').glob('*.json')).write_text('{broken',encoding='utf8')
    artifacts.prepared('declarations',['inventory-v1'],compute)
    assert len(calls)==3
    artifacts.prepared('declarations',['inventory-v2-new-egg-product'],compute)
    assert len(calls)==4


def test_defaults_preserve_old_serialization_and_per_meal_validation():
    assert 'recipe_choices' not in MealSettings().model_dump()
    assert 'max_same_base_meals' not in MealSettings().model_dump()
    with pytest.raises(ValueError):MealSettings(meal_type='breakfast',recipe_choices={'dinner_level':'simple'})
    with pytest.raises(ValueError):MealSettings(recipe_choices={'min_ingredients':8,'max_ingredients':4})


def test_final_week_check_rejects_base_repeat_on_swap_before_audit():
    recipe=_registered()[0]
    planner=SimpleNamespace(meals={'dinner':MealSettings(count=3,max_same_base_meals=2)},request=SimpleNamespace(recipe_preferences=RecipePreferences(mode='complete')))
    slots=[MealSlot(id=f'dinner-{day}',day=day,meal_type='dinner',recipe=recipe) for day in range(1,4)]
    with pytest.raises(ValueError,match='upprepningsgränsen'):PersonalPlanner._check_final(planner,slots,None,None,None,None)

def test_authored_quark_reuses_existing_exact_identity_rule():
    from app.services.complete_recipes import _whole_food_identity
    from app.services.personal_policy import ProductFacts

    from backend.tests.test_personal_planning_v2 import product
    p=product('Kvarg Naturell',500,'g',20)
    fact=ProductFacts(source='synthetic-regression',source_product_id=p.product_id,
        source_snapshot_id='unit',animal=True,ingredients=('MJÖLK, mjölksyrakultur',))
    assert _whole_food_identity('kvarg','as_sold',p,fact)
    assert not _whole_food_identity('kvarg','dry',p,fact)
    assert not _whole_food_identity('kvarg','as_sold',p.model_copy(update={'name':'Kvarg vanilj'}),fact)
    from dataclasses import replace
    assert not _whole_food_identity('kvarg','as_sold',p,replace(fact,ingredients=('MJÖLK, socker',)))

def test_imported_older_version_cannot_replace_newer_current(monkeypatch):
    from app.services.recipe_library import current_recipes
    recipe=_registered()[0]
    old=recipe.model_copy(update={'design':recipe.design.model_copy(update={'version':'1.0.0'})})
    new=recipe.model_copy(update={'design':recipe.design.model_copy(update={'version':'10.0.0'})})
    monkeypatch.setattr(content,'manifest_entries',lambda:{'current':[{}]})
    monkeypatch.setattr(content,'load_entries',lambda entries:(new,old))
    assert current_recipes()==(new,)

def test_null_design_does_not_hide_independent_valid_rows(tmp_path):
    path=pack(tmp_path);raw=json.loads(path.read_bytes());raw['recipes'].append({'design':None})
    path.write_bytes(content.encoded(raw));checked=content.validate_pack(path)
    assert len(checked['recipes'])==1 and len(checked['rejections'])==1
    assert checked['rejections'][0]['recipe_id']=='unknown'

def test_meal_choices_keep_explicit_products_only_adaptation():
    from app.services.recipe_library import matches_meal
    recipe=next(r for r in _registered() if r.design.variant_id!='base')
    meal=MealSettings(recipe_choices={'dinner_level':'crafted'})
    assert not matches_meal(recipe,meal,RecipePreferences(mode='complete',adaptation='products'))


def test_large_fact_projection_survives_process_reload_and_corruption(tmp_path,monkeypatch):
    monkeypatch.setenv('RECIPE_PREPARATION_CACHE_ROOT',str(tmp_path))
    value={'exact_evidence':['råvara och källa ' * 30000]}
    calls=[]
    def compute():calls.append(1);return value
    assert artifacts.prepared('source_facts','exact-source-v1',compute)==value
    envelope_path=next((tmp_path/'source_facts').glob('*.json'))
    envelope=json.loads(envelope_path.read_bytes())
    assert envelope['encoding']=='zlib-json-v1'
    assert artifacts.prepared('source_facts','exact-source-v1',compute)==value and len(calls)==1
    envelope['payload']='corrupt-compressed-payload'
    envelope_path.write_bytes(content.encoded(envelope))
    assert artifacts.prepared('source_facts','exact-source-v1',compute)==value and len(calls)==2


def test_declaration_inventory_binds_changed_rows_and_new_products(tmp_path,monkeypatch):
    from app.services import declaration_semantics

    from backend.tests.test_personal_planning_v2 import product
    monkeypatch.setenv('RECIPE_PREPARATION_CACHE_ROOT',str(tmp_path))
    calls=[]
    def classify(p,fact):calls.append(p.product_id);return 'bröd'
    monkeypatch.setattr(declaration_semantics,'declaration_food_class',classify)
    p=product('bröd',500,'g',20)
    facts=SimpleNamespace(version='same-explicit-facts-version')
    universe=SimpleNamespace(universe_id='same-source-id',products=(p,))
    assert artifacts.declaration_index(universe,facts,lambda p:None)=={0:'bröd'}
    artifacts.declaration_index(universe,facts,lambda p:None)
    assert len(calls)==1
    universe.products=(p.model_copy(update={'package_quantity':600}),)
    artifacts.declaration_index(universe,facts,lambda p:None)
    assert len(calls)==2
    universe.products=(*universe.products,product('annan vara',500,'g',30))
    assert artifacts.declaration_index(universe,facts,lambda p:None)=={0:'bröd',1:'bröd'}
    assert len(calls)==4


@pytest.mark.parametrize('category',['breakfast','snack'])
@pytest.mark.usefixtures("verified_smako_member")
def test_explicit_replacement_resolves_current_meal_type_before_week_recalculation(category,monkeypatch):
    import asyncio

    from app.api import personal as api
    from app.config import Settings
    from app.models import PlanRequest
    from app.models.personal import PersonalMutation
    from app.services import complete_recipes
    recipe=next(r for r in _registered() if category in r.design.meal_types)
    spec={'use_pantry':False,'meals':[{'meal_type':category,'count':1,'servings':recipe.servings,'recipe_choices':{}}]}
    request=PlanRequest(recipes=0,recipe_preferences={'mode':'complete'},personal=spec)
    slot=MealSlot(id=category+'-1',day=1,meal_type=category,recipe=recipe)
    saved=SimpleNamespace(revision=1,request=request,plan=SimpleNamespace(personal=SimpleNamespace(slots=[slot])))
    store=SimpleNamespace(get_owned=lambda *args,**kwargs:saved)
    state={'revision':0,'items':[],'reservations':{},'events':{}}
    private=SimpleNamespace(read=lambda owner:state,prepare_revision=lambda owner,saved:state)
    settings=Settings(complete_recipes_enabled=True)
    monkeypatch.setattr(api,'context',lambda *args:(settings,store,'synthetic-owner'))
    monkeypatch.setattr(api,'PersonalStore',lambda plans:private)
    monkeypatch.setattr(api,'GLOBAL_PREPARED_PRICE_UNIVERSES',SimpleNamespace(get_for_request=lambda *args:object()))
    async def reaches_week_recalculation(updated,*args,**kwargs):
        assert updated.personal.slots[0].recipe.design.base_id==recipe.design.base_id
        assert updated.personal.slots[0].meal_type==category
        raise ValueError('reached independent whole-week recalculation')
    monkeypatch.setattr(api,'_run_personal_work',reaches_week_recalculation)
    payload=PersonalMutation(revision=1,pantry_revision=0,action='replace',slot_id=slot.id,
        recipe_id=complete_recipes.identity(recipe))
    with pytest.raises(ValueError,match='reached independent whole-week'):
        asyncio.run(api._change_plan('synthetic-plan',payload,None,None))
