from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecipeRelevantIngredient:
    """Stable canonical ingredient identity used by normalization and benchmarks."""

    canonical: str
    queries: tuple[str, ...]


# This is the single identity vocabulary shared by ProductNormalizer, registry
# enrichment and catalog coverage benchmarks.  The Swedish query aliases are
# intentionally short and operator-readable; they are discovery hints, not a
# substitute for the normalizer's stricter product-identity evidence.
RECIPE_RELEVANT_INGREDIENTS: tuple[RecipeRelevantIngredient, ...] = (
    RecipeRelevantIngredient("milk", ("mjölk",)),
    RecipeRelevantIngredient("cream", ("grädde", "matlagningsgrädde")),
    RecipeRelevantIngredient("creme_fraiche", ("crème fraiche", "creme fraiche")),
    RecipeRelevantIngredient("butter", ("smör",)),
    RecipeRelevantIngredient("cheese", ("ost",)),
    RecipeRelevantIngredient("eggs", ("ägg",)),
    RecipeRelevantIngredient("potato", ("potatis",)),
    RecipeRelevantIngredient("ris", ("ris", "basmatiris")),
    RecipeRelevantIngredient("pasta", ("pasta", "spaghetti")),
    RecipeRelevantIngredient("nudlar", ("nudlar",)),
    RecipeRelevantIngredient("tortillas", ("tortilla",)),
    RecipeRelevantIngredient("bröd", ("bröd",)),
    RecipeRelevantIngredient("couscous", ("couscous",)),
    RecipeRelevantIngredient("chicken_meat", ("kyckling", "kycklingfilé", "kycklinglår")),
    RecipeRelevantIngredient("minced_beef", ("nötfärs",)),
    RecipeRelevantIngredient("meat_mince", ("blandfärs",)),
    RecipeRelevantIngredient("pork_meat", ("fläskkött", "fläsk")),
    RecipeRelevantIngredient("korv", ("korv",)),
    RecipeRelevantIngredient("falukorv", ("falukorv",)),
    RecipeRelevantIngredient("salmon", ("lax",)),
    RecipeRelevantIngredient("fish_meat", ("torsk", "vit fisk")),
    RecipeRelevantIngredient("tofu", ("tofu",)),
    RecipeRelevantIngredient("lentil", ("röda linser", "gröna linser")),
    RecipeRelevantIngredient("red_lentils", ("röda linser", "linser röda")),
    RecipeRelevantIngredient("kidney_bean", ("kidneybönor",)),
    RecipeRelevantIngredient("chickpeas", ("kikärtor",)),
    RecipeRelevantIngredient("yellow_onion", ("gul lök", "lök gul")),
    RecipeRelevantIngredient("garlic", ("vitlök",)),
    RecipeRelevantIngredient("carrot", ("morot", "morötter")),
    RecipeRelevantIngredient("pepper", ("röd paprika", "paprika")),
    RecipeRelevantIngredient("white_cabbage", ("vitkål", "kål")),
    RecipeRelevantIngredient("broccoli", ("broccoli",)),
    RecipeRelevantIngredient("cauliflower", ("blomkål",)),
    RecipeRelevantIngredient("tomato", ("tomat",)),
    RecipeRelevantIngredient("cucumber", ("gurka",)),
    RecipeRelevantIngredient("zucchini", ("zucchini", "squash")),
    RecipeRelevantIngredient("leek", ("purjolök",)),
    RecipeRelevantIngredient("mushroom", ("champinjoner", "svamp")),
    RecipeRelevantIngredient("krossade_tomater", ("krossade tomater",)),
    RecipeRelevantIngredient("tomato_puree", ("tomatpuré",)),
    RecipeRelevantIngredient("coconut_milk", ("kokosmjölk",)),
    RecipeRelevantIngredient("broth", ("buljong",)),
    RecipeRelevantIngredient("soy_sauce", ("sojasås", "soja")),
    RecipeRelevantIngredient("corn", ("majs",)),
    RecipeRelevantIngredient("peas", ("gröna ärtor", "ärtor")),
    RecipeRelevantIngredient("spinach", ("spenat",)),
    RecipeRelevantIngredient("celery", ("selleri",)),
    RecipeRelevantIngredient("cooking_oil", ("rapsolja", "matolja")),
)

RECIPE_RELEVANT_CANONICAL_FOODS = frozenset(
    ingredient.canonical for ingredient in RECIPE_RELEVANT_INGREDIENTS
)
RECIPE_QUERY_ALIASES = {
    ingredient.canonical: ingredient.queries for ingredient in RECIPE_RELEVANT_INGREDIENTS
}
