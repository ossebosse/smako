"""Messages for choices Smako cannot check yet say what happened and what to do (docs/UI-LANGUAGE.md)."""
from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSettings, PersonalPlanning, TasteProfile
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict, is_nonfood

from backend.tests.test_personal_planning_v2 import NOW, prepared, state


def planner(profile=None):
    request = PlanRequest(recipes=1, servings=2, personal=PersonalPlanning(profile=profile or TasteProfile(), meals=[MealSettings(count=1, servings=2)]))
    return PersonalPlanner(request, Settings(), prepared(), state(), facts={}, now=NOW)


def test_missing_declarations_name_what_to_remove_without_internal_terms():
    p = planner(TasteProfile(allergies=["gluten"], exclusions=["koriander"]))
    text = p._data_blocked_text(PolicyConflict("Nötfärs: fullständig spårbar ingrediens-/allergeninformation saknas.", stage="policy_taste", code="DATA_BLOCKED"), p.spec.meals[0])
    assert text.startswith("Vi har inte innehållsförteckningen för tillräckligt många varor för att säkert undvika gluten, koriander.")
    assert "Allergier eller Ät inte" in text
    for internal in ("spårbar", "proteinmål", "Orsaken visas", "hård uteslutning"):
        assert internal not in text


def test_weight_and_nutrition_blocks_point_at_their_own_choice():
    p = planner()
    weight = p._data_blocked_text(PolicyConflict("Färsbiffar: vi vet inte vad en färdig portion väger, så receptet kan inte kontrolleras mot en viktgräns.", stage="preparation", code="DATA_BLOCKED"), p.spec.meals[0])
    assert "färdig portion väger" in weight and "Ta bort gränsen för portionsvikt" in weight
    nutrition = p._data_blocked_text(PolicyConflict("Mjölk: näring saknas.", stage="nutrition", code="DATA_BLOCKED"), p.spec.meals[0])
    assert "Näringsvärden" in nutrition and "proteinmål" not in nutrition


def test_household_and_pet_items_are_not_food():
    for name in ("Batterier AA 4-pack", "Tändstickor Solstickan", "Våtservetter", "Bindor Normal", "Deodorant Roll-on",
                 "Rakblad 4-pack", "Finish Disktabletter", "First Price Paté Nöt Kattmat Våt", "Vov Hundmat", "Kattsand 10 l"):
        assert is_nonfood(name), name
    for name in ("Mjölk", "Tonfisk i vatten", "Kycklingfilé"):
        assert not is_nonfood(name), name
