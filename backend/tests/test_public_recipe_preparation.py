"""Prepared retrieval never replaces source, quantity or policy qualification."""
from unittest.mock import patch

from app.services import meal_prepared_artifacts as artifacts
from app.services.product_search import ProductSearchRequest

from backend.tests.test_personal_planning_v2 import prepared, product


def test_prepared_retrieval_matches_existing_alias_search_and_survives_restart(tmp_path, monkeypatch):
    from app.services.ingredient_normalizer import CANONICAL_ALIASES
    monkeypatch.setenv("RECIPE_PREPARATION_CACHE_ROOT", str(tmp_path))
    universe = prepared(product("Creme fraiche", 200, "g", 20))
    name = "crème fraiche"
    expected = set()
    for alias in (name, *CANONICAL_ALIASES.get(name, ())):
        keys, _, _ = universe.product_search_index.retrieve(ProductSearchRequest(query=alias))
        expected.update(i for key in keys for i in universe.product_search_index.groups[key])
    assert expected
    assert artifacts.ingredient_search_positions(universe, name, complete=True) == expected
    restored = universe.to_artifact().restore()
    before = artifacts.STATS["hits"]
    with patch.object(type(restored.product_search_index), "retrieve", side_effect=AssertionError("recomputed")):
        assert artifacts.ingredient_search_positions(restored, name, complete=True) == expected
    assert artifacts.STATS["hits"] > before
    assert not any("owner" in f.read_text() for f in (tmp_path / "ingredient-search").glob("*.json"))


def test_new_inventory_invalidates_negative_ingredient_search(tmp_path, monkeypatch):
    monkeypatch.setenv("RECIPE_PREPARATION_CACHE_ROOT", str(tmp_path))
    empty = prepared(product("Ris", 500, "g", 20))
    assert not artifacts.ingredient_search_positions(empty, "rapsolja", complete=True)
    added = prepared(product("Ris", 500, "g", 20), product("Rapsolja", 500, "ml", 20))
    assert artifacts.ingredient_search_positions(added, "rapsolja", complete=True)


def test_custom_query_and_legacy_mode_keep_existing_retrieval(tmp_path, monkeypatch):
    monkeypatch.setenv("RECIPE_PREPARATION_CACHE_ROOT", str(tmp_path))
    universe = prepared(product("Servetter", 20, "st", 10))
    expected, _, _ = universe.product_search_index.retrieve(ProductSearchRequest(query="Servetter"))
    positions = {i for key in expected for i in universe.product_search_index.groups[key]}
    for complete in (False, True):
        assert artifacts.ingredient_search_positions(universe, "Servetter", complete=complete) == positions


def test_corrupt_ingredient_artifact_recomputes_safely(tmp_path, monkeypatch):
    monkeypatch.setenv("RECIPE_PREPARATION_CACHE_ROOT", str(tmp_path))
    universe = prepared(product("Ris", 500, "g", 20))
    expected = artifacts.ingredient_search_positions(universe, "ris", complete=True)
    for path in (tmp_path / "ingredient-search").glob("*.json"):
        path.write_text('{"partial":', encoding="utf8")
    restored = universe.to_artifact().restore()
    before = artifacts.STATS["invalid"]
    assert artifacts.ingredient_search_positions(restored, "ris", complete=True) == expected
    assert artifacts.STATS["invalid"] > before
