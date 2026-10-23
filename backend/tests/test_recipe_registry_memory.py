"""Historical authority must survive sharing the current scaled registry."""

import gc
import weakref

import pytest
from app.models.recipe_preferences import RecipePreferences
from app.services import recipe_candidate_validator as validator
from app.services import recipe_library as library
from pydantic import BaseModel


def test_global_pure_id_cache_does_not_retain_finished_request_recipes():
    recipe = library._registered()[0].model_copy(deep=True)
    key, reference = id(recipe), weakref.ref(recipe)
    expected = validator.recipe_id(recipe)
    assert validator.recipe_id(recipe) == expected
    assert key in validator._RECIPE_IDS
    del recipe
    gc.collect()
    assert reference() is None
    assert key not in validator._RECIPE_IDS


def test_shared_authored_subtrees_are_recursively_frozen():
    def check(value):
        if isinstance(value, BaseModel):
            assert value.model_config.get("frozen")
            assert not value.model_extra
            for name in type(value).model_fields:
                check(getattr(value, name))
        elif isinstance(value, tuple):
            for item in value:
                check(item)
        else:
            assert type(value) in (str, int, float, bool, type(None))
    for recipe in library._registered():
        check(recipe.design)
        for ingredient in recipe.ingredients:
            check(ingredient)


def test_candidate_mutable_containers_remain_private():
    preferences = RecipePreferences(mode="complete")
    first = library.candidates(preferences, 4)[0]
    before = first.model_dump_json()
    first.instructions.append("Edited private instruction")
    first.ingredients.clear()
    first.preparation.input_forms.clear()
    second = library.candidates(preferences, 4)[0]
    assert second.model_dump_json() == before
    assert library.validate_recipe_design(second)


def test_history_reuses_current_portions_but_retains_distinct_issued_content(monkeypatch):
    source = library._registered()[0]
    current = library._scaled(source, 4)
    # A distinct source with the same claimed version must never borrow current
    # content. The issued index must still detect that conflicting publication.
    conflicting = source.model_copy(update={"name": source.name + " changed"})
    monkeypatch.setattr(library, "_registered", lambda: (source,))
    monkeypatch.setattr(library, "_registered_portions", lambda servings: (current,))
    monkeypatch.setattr(library, "_registered_history", lambda: (source, conflicting))
    # Isolate just structural validation to reach the index's independent
    # conflicting-publication check; normal structural validation rejects it too.
    monkeypatch.setattr(library, "_structural_check", lambda recipe: None)
    library._registered_historical_portions.cache_clear()
    library._issued_index.cache_clear()
    try:
        rows = library._registered_historical_portions(4)
        assert rows[0] is current
        assert rows[1].name == conflicting.name
        with pytest.raises(ValueError, match="Motstridigt innehåll"):
            library._issued_index(4)
    finally:
        library._registered_historical_portions.cache_clear()
        library._issued_index.cache_clear()


def test_shared_current_portions_still_receive_structural_validation(monkeypatch):
    source = library._registered()[0]
    damaged = library._scaled(source, 4)
    damaged.instructions.append("An unapproved mutable list edit")
    monkeypatch.setattr(library, "_registered", lambda: (source,))
    monkeypatch.setattr(library, "_registered_portions", lambda servings: (damaged,))
    monkeypatch.setattr(library, "_registered_history", lambda: (source,))
    library._registered_historical_portions.cache_clear()
    try:
        with pytest.raises(ValueError, match="Visade instruktioner"):
            library._registered_historical_portions(4)
    finally:
        library._registered_historical_portions.cache_clear()
