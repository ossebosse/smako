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
