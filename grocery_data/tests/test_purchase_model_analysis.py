from decimal import Decimal

from grocery_data.app.services.purchase_model_analysis import (
    _percent,
    is_recipe_relevant,
    package_pattern,
)


def test_package_pattern_groups_numeric_variants_without_guessing_meaning() -> None:
    assert package_pattern("ca 400 g") == "ca <n> g"
    assert package_pattern("Ca 1,2 kg") == "ca <n> kg"
    assert package_pattern(None) == "(missing)"


def test_recipe_relevant_classification_is_broad_and_excludes_non_food() -> None:
    assert is_recipe_relevant(("Skafferi", "Pasta")) is True
    assert is_recipe_relevant(("Djur", "Hundmat")) is False
    assert is_recipe_relevant(()) is False


def test_percent_rounds_half_up_and_handles_empty_denominator() -> None:
    assert _percent(1, 8) == Decimal("12.50")
    assert _percent(0, 0) == Decimal("0.00")
