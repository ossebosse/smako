from __future__ import annotations

from types import SimpleNamespace

import pytest
from app.models.recipe import Recipe, RecipeIngredient
from scripts.benchmark_planner_golden import (
    _contract_reference,
    _normalized_label,
    _recipe_semantics,
    _write_new,
    semantic_fingerprint,
)


def test_semantic_fingerprint_is_independent_of_mapping_order() -> None:
    left = {"basket": {"total": 12.5, "products": ["a", "b"]}, "recipes": 5}
    right = {"recipes": 5, "basket": {"products": ["a", "b"], "total": 12.5}}

    assert semantic_fingerprint(left) == semantic_fingerprint(right)
    assert semantic_fingerprint(left) != semantic_fingerprint(
        {"basket": {"total": 12.6, "products": ["a", "b"]}, "recipes": 5}
    )


def test_recipe_economic_semantics_normalizes_display_ingredient_order() -> None:
    ingredients = [
        RecipeIngredient(name="Ris", canonical_name="rice", quantity=300, unit="g"),
        RecipeIngredient(name="Lök", canonical_name="onion", quantity=100, unit="g"),
    ]
    left = Recipe(
        name="Gryta",
        servings=4,
        ingredients=ingredients,
        instructions=["Koka."],
    )
    right = Recipe(
        name="Gryta",
        servings=4,
        ingredients=list(reversed(ingredients)),
        instructions=["En annan displaytext."],
    )

    assert _recipe_semantics(left) == _recipe_semantics(right)


def test_regular_contract_reference_is_stable_and_source_backed() -> None:
    item = SimpleNamespace(
        price_contract_id=None,
        store_id="context:chain:store",
        product_id="product-1",
        source_provenance=SimpleNamespace(source_snapshot_id="snapshot-1"),
    )

    first = _contract_reference(item)
    second = _contract_reference(item)

    assert first == second
    assert first[0].startswith("price-contract:")
    assert first[1] == "derived_regular_contract_identity"


def test_frozen_golden_is_never_overwritten(tmp_path) -> None:
    target = tmp_path / "golden.json"
    _write_new(target, {"semantic_fingerprint": "first"})

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        _write_new(target, {"semantic_fingerprint": "second"})

    assert "first" in target.read_text(encoding="utf-8")


def test_golden_label_is_safe_and_deterministic() -> None:
    assert _normalized_label("Store Cap V1") == "-store-cap-v1"
    assert _normalized_label(None) == ""

    with pytest.raises(ValueError, match="golden label"):
        _normalized_label("../replace-existing")
