"""Ordinary measured cold breakfasts/snacks using existing product declarations.

No density, draining yield or generic nutrition is assumed. The narrow plain
quark identity review extends the dinner taxonomy locally, not the price source.
"""

import re

from app.models.recipe import Recipe, RecipeIngredient
from app.services.ingredient_normalizer import canonicalize_ingredient_name

VERSION = "cold-quark-assembly-20260913"
STEPS = [
    "Väg upp naturell kvarg som såld enligt ingredienslistan. Rör om och skeda upp i en skål; häll inte av vätska. Använd inte smaksatt kvarg, kvargdryck eller dessert.",
    "Väg bröd och ost om de ingår i listan. Lägg osten på brödet och servera tillsammans med kvargen. Ingen uppvärmning eller avrinning ingår; inga olistade ingredienser tillsätts.",
    "Servera hela den uppmätta ätbara mängden jämnt fördelad mellan portionerna. Överbliven mat i förpackningarna ingår inte i portionsberäkningen.",
]
TEMPLATES = {
    "breakfast": [
        ("Naturell kvarg med bröd", [("kvarg", 250), ("bröd", 80)]),
        ("Naturell kvarg och ostsmörgås", [("kvarg", 200), ("bröd", 80), ("ost", 20)]),
    ],
    "snack": [
        ("Naturell kvarg", [("kvarg", 200)]),
        ("Kvarg med liten ostsmörgås", [("kvarg", 150), ("bröd", 40), ("ost", 20)]),
    ],
}


def candidates(meal_type, servings):
    return [
        Recipe(
            name=name,
            servings=servings,
            ingredients=[
                RecipeIngredient(name=n, quantity=q * servings, unit="g") for n, q in ingredients
            ],
            instructions=STEPS,
        )
        for name, ingredients in TEMPLATES.get(meal_type, [])
    ]


def preparation(recipe):
    names = {canonicalize_ingredient_name(i.name) for i in recipe.ingredients}
    return (
        recipe.instructions == STEPS
        and "kvarg" in names
        and names <= {"kvarg", "bröd", "ost"}
        and len(names) == len(recipe.ingredients)
        and all(i.unit == "g" for i in recipe.ingredients)
    )


def plain_quark(product, facts):
    """Name/form evidence plus retained dairy composition; never brand or price joins."""
    text = product.name.casefold().strip()
    return bool(
        re.fullmatch(
            r"(?:laktosfri )?(?:mild )?kvarg (?:mild )?naturell(?: (?:eko|ekologisk))?(?: \d+(?:[,.]\d+)?%)?",
            text,
        )
        and product.usable_unit == "g"
        and facts
        and facts.animal is True
        and facts.ingredients
        and not facts.conflicts
        and facts.nutrition_preparation == "as_sold"
        and not any(
            t in " ".join(facts.ingredients).casefold()
            for t in ("arom", "socker", "sötningsmedel", "frukt", "bär")
        )
    )
