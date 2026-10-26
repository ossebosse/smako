"""Actual ordinary resolve path; source scope and whole-food gates retained."""
import pytest
from app.config import Settings
from app.models import PlanRequest
from app.models.personal import TasteProfile
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict
from app.services.recipe_library import current_recipes

from backend.tests.test_personal_planning_v2 import NOW, prepared, product, state


@pytest.mark.parametrize('label,accepted',[('Kokos Riven',True),('Riven Kokos',True),
    ('Kokos Riven Ekologisk',True),('Kokos Riven Sötad',False),('Kokosmjöl',False),
    ('Kokosmjölk',False),('Kokosolja',False),('Choklad med Riven Kokos',False)])
def test_coconut_alias_keeps_all_recipe_and_quantity_gates(label,accepted):
    recipe=next(r for r in current_recipes() if any(i.canonical_name=='kokosflingor' and i.form=='dry' for i in r.ingredients))
    p=prepared(product(label,200,'g',10,brand='Test').model_copy(update={'category':'Skafferi Nötter och kokos'}))
    req=PlanRequest(recipe_preferences={'mode':'complete'},personal={'meals':[{'count':1,'servings':4}]})
    planner=PersonalPlanner(req,Settings(price_provider='mock',complete_recipes_enabled=True),p,state(),facts={},now=NOW)
    def resolve():return planner.resolve('kokosflingor',5,'g',profile=TasteProfile(),organic_animals=False,recipe=recipe)
    if accepted:
        rows=resolve()
        assert len(rows)==1 and rows[0][1].usable_quantity==200 and rows[0][1].quantity_confidence=='exact'
    else:
        with pytest.raises(PolicyConflict):resolve()


def test_compound_dessert_is_not_a_generic_coconut_purchase():
    p=prepared(product('Choklad med Riven Kokos',200,'g',10))
    planner=PersonalPlanner(PlanRequest(personal={'meals':[]}),Settings(price_provider='mock'),p,state(),facts={},now=NOW)
    with pytest.raises(PolicyConflict):
        planner.resolve('kokosflingor',5,'g',profile=TasteProfile(),organic_animals=False)
