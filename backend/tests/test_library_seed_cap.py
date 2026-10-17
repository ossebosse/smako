from types import SimpleNamespace

import pytest
from app.services.stable_candidate_pool import library_seed_cap


def _recipe(name, cuisine):
    return SimpleNamespace(name=name, design=SimpleNamespace(cuisines=(cuisine,)))


@pytest.fixture(autouse=True)
def _ids(monkeypatch):
    monkeypatch.setattr("app.services.stable_candidate_pool.recipe_id", lambda r: r.name)


def _evidence(paid, packages=()):
    return SimpleNamespace(paid=paid, packages=frozenset(packages))


def test_small_pool_is_unchanged():
    recipes = [_recipe(f"r{i}", "thai") for i in range(5)]
    assert library_seed_cap(recipes, {r.name: _evidence(i) for i, r in enumerate(recipes)}, limit=10) == recipes


def test_keeps_cheapest_overlap_and_each_cuisine_in_original_order():
    recipes = [_recipe(f"thai{i}", "thai") for i in range(10)] + [_recipe("dyr-grekisk", "greek")]
    evidence = {r.name: _evidence(100 + i) for i, r in enumerate(recipes)}
    evidence["dyr-grekisk"] = _evidence(900)
    evidence["thai9"] = _evidence(500, {("s", "delad"), ("s", "x")})
    evidence["thai8"] = _evidence(510, {("s", "delad")})

    kept = library_seed_cap(recipes, evidence, limit=5)

    names = [r.name for r in kept]
    assert "dyr-grekisk" in names  # the two cheapest of every cuisine
    assert "thai9" in names  # strongest shared packages
    assert {"thai0", "thai1"} <= set(names)  # cheapest single purchases
    assert names == [r.name for r in recipes if r.name in names]


def test_recipes_without_evidence_are_always_kept():
    recipes = [_recipe(f"r{i}", "thai") for i in range(8)]
    evidence = {r.name: _evidence(i) for r, i in zip(recipes[:6], range(6), strict=True)}
    names = {r.name for r in library_seed_cap(recipes, evidence, limit=3)}
    assert {"r6", "r7"} <= names


def test_limit_must_be_positive():
    with pytest.raises(ValueError):
        library_seed_cap([], {}, limit=0)
