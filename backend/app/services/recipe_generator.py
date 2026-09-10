"""Recipe generation is isolated from every price calculation.

The generator may decide *what* to cook, but it never returns or calculates a
price. Structured price data is only supplied as an economic signal.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any

from app.models.recipe import Recipe, RecipeCollection, RecipeIngredient


class RecipeGenerator(ABC):
    @abstractmethod
    def generate_recipes(
        self,
        cheap_ingredients: Iterable[Any],
        count: int = 5,
        servings: int = 4,
    ) -> list[Recipe]:
        """Generate exactly ``count`` recipes with ``servings`` portions."""

    def improve_recipes(
        self,
        recipes: list[Recipe],
        cost_feedback: dict[str, Any],
        cheap_ingredients: Iterable[Any],
        servings: int = 4,
    ) -> list[Recipe]:
        """Optional second pass. The deterministic caller decides if it is better."""

        return recipes


def _ingredient(name: str, quantity: float, unit: str) -> RecipeIngredient:
    return RecipeIngredient(name=name, quantity=quantity, unit=unit)


def _scale_recipe(recipe: Recipe, servings: int) -> Recipe:
    factor = servings / recipe.servings
    ingredients = [
        ingredient.model_copy(
            update={"quantity": round(ingredient.quantity * factor, 2)}, deep=True
        )
        for ingredient in recipe.ingredients
    ]
    return recipe.model_copy(
        update={"servings": servings, "ingredients": ingredients}, deep=True
    )


class MockRecipeGenerator(RecipeGenerator):
    """Deterministic Swedish weekday recipes for keyless end-to-end operation."""

    def __init__(self) -> None:
        self._recipes = [
            Recipe(
                name="Krämig kycklingpasta med broccoli",
                servings=4,
                ingredients=[
                    _ingredient("kycklinglårfilé", 600, "g"),
                    _ingredient("pasta", 350, "g"),
                    _ingredient("fryst broccoli", 300, "g"),
                    _ingredient("crème fraiche", 200, "ml"),
                    _ingredient("gul lök", 150, "g"),
                ],
                instructions=[
                    "Koka pastan enligt förpackningen.",
                    "Skär kycklingen och löken, stek dem genomlagade i neutral olja.",
                    "Tillsätt broccoli och crème fraiche och låt sjuda i fem minuter.",
                    "Vänd ner pastan och smaka av med salt och peppar.",
                ],
            ),
            Recipe(
                name="Röd linsgryta med kokos och ris",
                servings=4,
                ingredients=[
                    _ingredient("röda linser", 300, "g"),
                    _ingredient("ris", 300, "g"),
                    _ingredient("krossade tomater", 500, "g"),
                    _ingredient("kokosmjölk", 400, "ml"),
                    _ingredient("morot", 300, "g"),
                    _ingredient("gul lök", 150, "g"),
                ],
                instructions=[
                    "Koka riset enligt förpackningen.",
                    "Hacka lök och morot och fräs dem mjuka i neutral olja.",
                    "Rör ner linser, krossade tomater och kokosmjölk.",
                    "Sjud tills linserna är mjuka och servera med ris.",
                ],
            ),
            Recipe(
                name="Ugnsrostad falukorv med potatis och morot",
                servings=4,
                ingredients=[
                    _ingredient("falukorv", 500, "g"),
                    _ingredient("potatis", 1000, "g"),
                    _ingredient("morot", 400, "g"),
                    _ingredient("gul lök", 150, "g"),
                ],
                instructions=[
                    "Sätt ugnen på 225 grader.",
                    "Skär potatis, morot, lök och korv i jämna bitar.",
                    "Blanda med neutral olja, salt och peppar på en plåt.",
                    "Rosta i cirka 30 minuter och vänd efter halva tiden.",
                ],
            ),
            Recipe(
                name="Stekt ris med ägg och grönsaker",
                servings=4,
                ingredients=[
                    _ingredient("ris", 320, "g"),
                    _ingredient("ägg", 8, "st"),
                    _ingredient("frysta grönsaker", 500, "g"),
                    _ingredient("vitkål", 300, "g"),
                    _ingredient("gul lök", 150, "g"),
                ],
                instructions=[
                    "Koka riset och låt det ånga av.",
                    "Strimla kål och lök och stek med de frysta grönsakerna.",
                    "Skjut grönsakerna åt sidan, knäck i äggen och rör tills de stelnat.",
                    "Vänd ner riset och smaka av med salt och peppar.",
                ],
            ),
            Recipe(
                name="Bönchili med tortillas",
                servings=4,
                ingredients=[
                    _ingredient("kidneybönor", 760, "g"),
                    _ingredient("krossade tomater", 800, "g"),
                    _ingredient("morot", 300, "g"),
                    _ingredient("gul lök", 150, "g"),
                    _ingredient("tortillas", 8, "st"),
                    _ingredient("crème fraiche", 200, "ml"),
                ],
                instructions=[
                    "Hacka lök och morot och fräs dem mjuka i neutral olja.",
                    "Skölj bönorna och tillsätt dem tillsammans med tomaterna.",
                    "Låt chilin sjuda i 15 minuter och smaka av med salt och peppar.",
                    "Värm tortillas och servera med chili och crème fraiche.",
                ],
            ),
            Recipe(
                name="Tomatig pastagratäng med linser",
                servings=4,
                ingredients=[
                    _ingredient("pasta", 400, "g"),
                    _ingredient("röda linser", 250, "g"),
                    _ingredient("krossade tomater", 600, "g"),
                    _ingredient("riven ost", 150, "g"),
                    _ingredient("gul lök", 150, "g"),
                ],
                instructions=[
                    "Koka pasta och linser nästan färdiga var för sig.",
                    "Fräs löken och blanda med krossade tomater, pasta och linser.",
                    "Lägg allt i en form, strö över ost och gratinera vid 225 grader.",
                ],
            ),
            Recipe(
                name="Potatis- och äggpanna med vitkål",
                servings=4,
                ingredients=[
                    _ingredient("potatis", 900, "g"),
                    _ingredient("ägg", 8, "st"),
                    _ingredient("vitkål", 500, "g"),
                    _ingredient("gul lök", 150, "g"),
                    _ingredient("mjölk", 200, "ml"),
                ],
                instructions=[
                    "Tärna potatisen och stek den mjuk under lock.",
                    "Tillsätt strimlad kål och lök och stek tills allt fått färg.",
                    "Vispa ägg och mjölk, häll över och låt stelna på låg värme.",
                ],
            ),
        ]

    def generate_recipes(
        self,
        cheap_ingredients: Iterable[Any],
        count: int = 5,
        servings: int = 4,
    ) -> list[Recipe]:
        if count < 1 or count > len(self._recipes):
            raise ValueError(f"Mockgeneratorn stöder 1–{len(self._recipes)} recept")

        cheap_names = " ".join(
            str(
                getattr(item, "canonical_name", None)
                or getattr(item, "ingredient", None)
                or (item.get("ingredient") if isinstance(item, dict) else "")
                or getattr(item, "product_name", None)
                or getattr(item, "name", "")
            ).lower()
            for item in cheap_ingredients
        )

        # Price data affects selection even in keyless mode: recipes sharing more
        # currently cheap ingredients are considered first. Stable index breaks ties.
        ranked = sorted(
            enumerate(self._recipes),
            key=lambda pair: (
                -sum(
                    1
                    for ingredient in pair[1].ingredients
                    if ingredient.name.lower() in cheap_names
                    or any(part in cheap_names for part in ingredient.name.lower().split())
                ),
                pair[0],
            ),
        )
        return [_scale_recipe(recipe, servings) for _, recipe in ranked[:count]]


class OpenAIRecipeGenerator(RecipeGenerator):
    """OpenAI Responses API implementation using Pydantic structured output."""

    def __init__(self, api_key: str, model: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self._model = model

    @staticmethod
    def _serialise_signal(cheap_ingredients: Iterable[Any]) -> str:
        payload: list[dict[str, Any]] = []
        for item in cheap_ingredients:
            if isinstance(item, dict):
                data = item
            elif hasattr(item, "model_dump"):
                data = item.model_dump(mode="json")
            else:
                data = {"ingredient": str(item)}
            payload.append(data)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    @staticmethod
    def _validate(result: RecipeCollection, count: int, servings: int) -> list[Recipe]:
        if len(result.recipes) != count:
            raise ValueError(f"Modellen returnerade {len(result.recipes)} recept, väntade {count}")
        if any(recipe.servings != servings for recipe in result.recipes):
            raise ValueError("Modellen returnerade fel portionsantal")
        if len({recipe.name.casefold() for recipe in result.recipes}) != count:
            raise ValueError("Modellen returnerade dubbletter")
        return result.recipes

    def generate_recipes(
        self,
        cheap_ingredients: Iterable[Any],
        count: int = 5,
        servings: int = 4,
    ) -> list[Recipe]:
        signal = self._serialise_signal(cheap_ingredients)
        response = self._client.responses.parse(
            model=self._model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Du skapar kostnadseffektiva, normala svenska vardagsmiddagar. "
                        "Returnera endast receptstrukturen. Du får aldrig hitta på, ange eller "
                        "räkna priser, butiker, produkter eller förpackningar."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Skapa exakt {count} olika middagsrecept för exakt {servings} portioner "
                        "per recept. Prioritera råvarorna i prisdatan nedan och återanvänd billiga "
                        "råvaror när det sänker kostnaden. Undvik specialingredienser och gör ändå "
                        "rimliga, varierade måltider. Anta att användaren endast har salt, peppar, "
                        "vatten och neutral matolja hemma. Alla övriga ingredienser måste listas. "
                        "Använd mängder som kan normaliseras till g, ml eller st; använd helst gram "
                        "för grönsaker som säljs per vikt och ml för crème fraiche och andra "
                        "flytande mejerivaror. Prisdata (endast ekonomisk signal):\n"
                        + signal
                    ),
                },
            ],
            text_format=RecipeCollection,
        )
        if response.output_parsed is None:
            raise ValueError("OpenAI returnerade inget strukturerat receptsvar")
        return self._validate(response.output_parsed, count, servings)

    def improve_recipes(
        self,
        recipes: list[Recipe],
        cost_feedback: dict[str, Any],
        cheap_ingredients: Iterable[Any],
        servings: int = 4,
    ) -> list[Recipe]:
        response = self._client.responses.parse(
            model=self._model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Du förbättrar en svensk veckomeny utifrån deterministiskt beräknad "
                        "kostnadsfeedback. Returnera bara recept. Upprepa aldrig priser i svaret "
                        "och gör inga egna prisberäkningar."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Föreslå en komplett, billigare version av samma antal middagar. Byt dyra "
                        "ingredienser/recept, återanvänd billiga råvaror och behåll rimliga "
                        f"vardagsmiddagar med exakt {servings} portioner. Använd g, ml eller st, "
                        "och ange crème fraiche och andra flytande mejerivaror i ml.\n"
                        "Nuvarande recept:\n"
                        + json.dumps(
                            [recipe.model_dump(mode="json") for recipe in recipes],
                            ensure_ascii=False,
                        )
                        + "\nBackendens kostnadsfeedback:\n"
                        + json.dumps(cost_feedback, ensure_ascii=False)
                        + "\nBilliga råvaror:\n"
                        + self._serialise_signal(cheap_ingredients)
                    ),
                },
            ],
            text_format=RecipeCollection,
        )
        if response.output_parsed is None:
            raise ValueError("OpenAI returnerade inget strukturerat förbättringssvar")
        return self._validate(response.output_parsed, len(recipes), servings)
