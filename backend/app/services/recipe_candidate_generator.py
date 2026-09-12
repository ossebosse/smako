"""Generate a broad, price-informed set of recipe candidates.

Candidate generation deliberately has no basket or pricing responsibility.  A
local economic ingredient pool is supplied as a signal, and the exact products
and prices are still selected deterministically later in the pipeline.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from app.models.recipe import Recipe, RecipeCollection, RecipeIngredient
from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.ingredient_taxonomy import (
    IngredientCategory,
    IngredientTaxonomyEntry,
    get_taxonomy_entry,
)


class RecipeCandidateGenerator(ABC):
    """Common contract for deterministic and LLM-backed candidate generation."""

    @abstractmethod
    def generate_candidates(
        self,
        economic_ingredients: Iterable[Any] | Any,
        count: int = 80,
        servings: int = 4,
    ) -> list[Recipe]:
        """Return exactly ``count`` distinct candidate recipes."""

    def generate_replacement_candidates(
        self,
        current_recipes: Sequence[Recipe],
        cost_feedback: dict[str, Any],
        economic_ingredients: Iterable[Any] | Any,
        count: int = 10,
        servings: int = 4,
    ) -> list[Recipe]:
        """Optionally propose replacements; backend pricing decides acceptance.

        The no-op default keeps deterministic/custom candidate generators
        backwards compatible. The optimized service only invokes this hook
        when an OpenAI key is configured.
        """

        return []

    @property
    def batch_statistics(self) -> dict[str, int]:
        """Return accepted candidates grouped by generation bias/family."""

        return {}


@dataclass(frozen=True, slots=True)
class CandidateBatch:
    """One logical OpenAI generation bias and its relative target share."""

    name: str
    weight: int
    instruction: str
    dish_forms: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("candidate batch name cannot be empty")
        if self.weight < 1:
            raise ValueError("candidate batch weight must be at least one")
        if not self.instruction.strip():
            raise ValueError("candidate batch instruction cannot be empty")
        if any(not dish_form.strip() for dish_form in self.dish_forms):
            raise ValueError("candidate batch dish forms cannot be empty")


DEFAULT_CANDIDATE_BATCHES: tuple[CandidateBatch, ...] = (
    CandidateBatch(
        "lowest_cost",
        40,
        "Optimera aggressivt kring de högst rankade billiga råvarorna och håll recepten korta.",
        ("gryta", "matig soppa", "chili"),
    ),
    CandidateBatch(
        "cheap_protein",
        40,
        "Centrera rätterna kring flera olika billiga protein-, ägg- och baljväxtkällor.",
        ("husmanskost/tallriksrätt", "ugnsplåt", "wok"),
    ),
    CandidateBatch(
        "vegetarian",
        30,
        "Skapa billiga vegetariska vardagsmiddagar med baljväxter, tofu eller ägg.",
        ("curry", "gratäng", "bowl"),
    ),
    CandidateBatch(
        "weekday",
        40,
        "Skapa igenkännbara svenska eller europeiska vardagsmiddagar med tydligt olika tillagningssätt.",
        ("pastarätt", "risrätt", "potatisrätt"),
    ),
    CandidateBatch(
        "reuse",
        40,
        "Utforma rätter som kan dela vanliga råvaror och använda rester från hela inköpsförpackningar.",
        ("nudelrätt", "wraps/tacos", "pytt eller stekpannerätt"),
    ),
)


def _allocate_candidate_batches(
    count: int, batches: Sequence[CandidateBatch]
) -> list[tuple[CandidateBatch, int]]:
    """Allocate exactly ``count`` candidates with deterministic largest remainders."""

    total_weight = sum(batch.weight for batch in batches)
    raw = [count * batch.weight / total_weight for batch in batches]
    allocated = [int(value) for value in raw]
    remainder = count - sum(allocated)
    order = sorted(
        range(len(batches)),
        key=lambda index: (-(raw[index] - allocated[index]), index),
    )
    for index in order[:remainder]:
        allocated[index] += 1
    return [
        (batch, target)
        for batch, target in zip(batches, allocated, strict=True)
        if target > 0
    ]


@dataclass(frozen=True, slots=True)
class _PoolIngredient:
    canonical: str
    entry: IngredientTaxonomyEntry
    rank: int


@dataclass(frozen=True, slots=True)
class _CandidateSpec:
    primary: _PoolIngredient
    carbohydrate: _PoolIngredient
    vegetable: _PoolIngredient
    family: str
    extras: tuple[_PoolIngredient, ...]
    rank_score: int


_FAMILY_ORDER: tuple[str, ...] = (
    "gryta",
    "pasta",
    "ugn",
    "wok",
    "chili",
    "curry",
    "panna",
    "gratäng",
    "soppa",
    "bowl",
    "wrap",
    "risrätt",
    "nudelrätt",
    "potatisrätt",
    "husman",
)


def _pool_rows(source: Iterable[Any] | Any) -> list[Any]:
    rows = getattr(source, "ingredients", source)
    if isinstance(rows, dict):
        return list(rows.values())
    try:
        return list(rows)
    except TypeError as exc:
        raise TypeError("economic_ingredients must be iterable or expose .ingredients") from exc


def _value(row: Any, *names: str) -> Any:
    for name in names:
        if isinstance(row, dict) and row.get(name) is not None:
            return row[name]
        value = getattr(row, name, None)
        if value is not None:
            return value
    return None


def _extract_pool(source: Iterable[Any] | Any) -> list[_PoolIngredient]:
    result: list[_PoolIngredient] = []
    seen: set[str] = set()
    for rank, row in enumerate(_pool_rows(source)):
        raw_name = _value(row, "canonical", "canonical_name", "ingredient", "name")
        if not raw_name:
            continue
        canonical = canonicalize_ingredient_name(str(raw_name))
        if canonical in seen:
            continue
        entry = get_taxonomy_entry(canonical)
        if entry is None:
            continue
        seen.add(canonical)
        result.append(_PoolIngredient(canonical=canonical, entry=entry, rank=rank))
    return result


def _families_for(
    primary: _PoolIngredient,
    carbohydrate: _PoolIngredient,
) -> tuple[str, ...]:
    carb = carbohydrate.canonical
    primary_is_legume = primary.entry.category == IngredientCategory.LEGUME
    primary_is_egg = primary.canonical == "ägg"

    if primary_is_egg:
        if carb == "pasta":
            return ("pasta", "gratäng")
        if carb == "potatis":
            return ("panna", "gratäng", "husman")
        if carb in {"ris", "nudlar"}:
            return ("wok", "panna")
        if carb == "tortillas":
            return ("wrap", "panna")
        return ("panna", "bowl")
    if carb == "pasta":
        return ("pasta", "gratäng", "gryta")
    if carb == "potatis":
        if primary_is_legume:
            return ("gryta", "soppa", "gratäng", "bowl", "potatisrätt")
        return (
            "ugn",
            "panna",
            "gratäng",
            "gryta",
            "soppa",
            "potatisrätt",
            "husman",
        )
    if carb == "ris":
        families = ["wok", "gryta", "curry", "bowl"]
        if primary_is_legume:
            families.insert(0, "chili")
        families.append("risrätt")
        return tuple(families)
    if carb == "nudlar":
        families = ["nudelrätt", "wok", "gryta", "curry", "bowl"]
        if primary_is_legume:
            families.insert(1, "chili")
        return tuple(families)
    if carb == "tortillas":
        return ("wrap", "chili") if primary_is_legume else ("wrap", "panna")
    if carb == "couscous":
        return ("bowl", "gryta", "panna")
    if carb == "bröd":
        return ("soppa", "panna", "bowl")
    return ("gryta", "panna", "bowl")


def _choose_extras(
    family: str,
    rows_by_category: dict[IngredientCategory, list[_PoolIngredient]],
    vegetables: Sequence[_PoolIngredient],
    vegetable_index: int,
    salt: int,
) -> tuple[_PoolIngredient, ...]:
    sauces = rows_by_category.get(IngredientCategory.SAUCE_BASE, [])
    dairy = rows_by_category.get(IngredientCategory.DAIRY, [])
    support = rows_by_category.get(IngredientCategory.FLAVOUR_SUPPORT, [])

    preferred: list[str]
    if family == "chili":
        preferred = ["krossade tomater", "tomatpuré"]
    elif family == "curry":
        preferred = ["kokosmjölk", "krossade tomater"]
    elif family in {"pasta", "gratäng"}:
        preferred = ["krossade tomater", "grädde", "crème fraiche", "ost"]
    elif family == "soppa":
        preferred = ["krossade tomater", "mjölk", "grädde", "buljong"]
    elif family == "wok":
        preferred = ["sojasås", "vitlök"]
    elif family in {"wrap", "bowl"}:
        preferred = ["crème fraiche", "krossade tomater", "majs"]
    else:
        preferred = ["vitlök", "krossade tomater", "crème fraiche"]

    available = {row.canonical: row for row in (*sauces, *dairy, *support, *vegetables)}
    extras: list[_PoolIngredient] = []
    for name in preferred:
        row = available.get(name)
        if row is not None:
            extras.append(row)
            break

    # A second vegetable improves both meal quality and profile diversity.  It
    # is selected deterministically from the economic ordering.
    if len(vegetables) > 1:
        other = vegetables[(vegetable_index + salt + 1) % len(vegetables)]
        if all(other.canonical != row.canonical for row in extras):
            extras.append(other)
    return tuple(extras)


def _ingredient_quantity(row: _PoolIngredient, servings: int) -> float:
    quantity = row.entry.typical_meal_quantity * servings / 4
    return round(quantity, 2)


def _make_ingredient(row: _PoolIngredient, servings: int) -> RecipeIngredient:
    return RecipeIngredient(
        name=row.entry.display_name,
        canonical_name=row.canonical,
        quantity=_ingredient_quantity(row, servings),
        unit=row.entry.expected_unit,
    )


def _recipe_name(spec: _CandidateSpec) -> str:
    primary = spec.primary.entry.display_name
    carb = spec.carbohydrate.entry.display_name
    vegetable = spec.vegetable.entry.display_name
    extras = {row.canonical for row in spec.extras}
    if spec.family == "pasta":
        if extras & {"grädde", "crème fraiche", "ost"}:
            return f"Krämig pasta med {primary} och {vegetable}"
        if extras & {"krossade tomater", "tomatpuré"}:
            return f"Tomatpasta med {primary} och {vegetable}"
        return f"Pasta med {primary} och {vegetable}"
    if spec.family == "wrap":
        return f"Tacos med {primary} och {vegetable}"
    if spec.family == "gryta":
        return f"Mustig gryta på {primary} med {carb} och {vegetable}"
    if spec.family == "ugn":
        return f"Ugnsplåt med {primary}, {carb} och {vegetable}"
    if spec.family == "wok":
        return f"Wok med {primary}, {carb} och {vegetable}"
    if spec.family == "chili":
        return f"Tomatgryta på {primary} med {carb} och {vegetable}"
    if spec.family == "curry":
        return f"Gryta med {primary}, {carb} och {vegetable}"
    if spec.family == "panna":
        if spec.carbohydrate.canonical == "potatis":
            return f"Pytt med {primary}, potatis och {vegetable}"
        if spec.carbohydrate.canonical == "tortillas":
            return f"Tortillapanna med {primary} och {vegetable}"
        return f"{primary.capitalize()}panna med {carb} och {vegetable}"
    if spec.family == "gratäng":
        if spec.carbohydrate.canonical == "potatis":
            return f"Potatisgratäng med {primary} och {vegetable}"
        if spec.carbohydrate.canonical == "pasta":
            return f"Pastagratäng med {primary} och {vegetable}"
        return f"Gratäng med {primary}, {carb} och {vegetable}"
    if spec.family == "soppa":
        return f"Matig soppa med {primary}, {carb} och {vegetable}"
    if spec.family == "bowl":
        return f"Bowl med {primary}, {carb} och {vegetable}"
    if spec.family == "risrätt":
        return f"Stekt ris med {primary} och {vegetable}"
    if spec.family == "nudelrätt":
        return f"Nudlar med {primary} och {vegetable}"
    if spec.family == "potatisrätt":
        return f"Stekt potatis med {primary} och {vegetable}"
    if spec.family == "husman":
        return f"Stekt {primary} med {carb} och {vegetable}"
    raise ValueError(f"Unsupported recipe family: {spec.family}")


def _instructions(spec: _CandidateSpec, servings: int) -> list[str]:
    primary = spec.primary.entry.display_name
    carb = spec.carbohydrate.entry.display_name
    vegetable = spec.vegetable.entry.display_name
    family = spec.family
    prep = (
        f"Mät upp alla ingredienser för {servings} portioner. Skölj och skär {vegetable} "
        "och övriga listade grönsaker i jämna bitar. Basvaror: vatten, salt, peppar "
        "och neutral matolja; inga andra olistade ingredienser behövs."
    )
    if spec.primary.entry.category == IngredientCategory.LEGUME:
        protein = (f"Förbered {primary}. Väg den listade mängden i produktens inköpsform. "
                   "Torra baljväxter blötläggs vid behov och kokas helt mjuka enligt "
                   "förpackningen; redan kokta sköljs och får rinna av.")
    elif spec.primary.canonical == "ägg":
        protein = "Knäck de listade äggen i en skål och vispa ihop."
    else:
        protein = f"Skär {primary} i mindre, jämna bitar."
    finish = "Kontrollera att proteinråvaran är genomlagad och grönsakerna mjuka. Smaka av med salt och peppar."
    if family == "ugn":
        steps = [
            "Värm ugnen till 225 grader. Skär potatis i 2 cm bitar; andra gryn kokas enligt förpackningen och serveras separat.",
            "Lägg potatis och grönsaker glest på en plåt med lite matolja. Rosta i ugn 20 minuter, vänd och tillsätt proteinråvaran och övriga listade ingredienser.",
            "Rosta ytterligare 15–25 minuter tills potatisen är mjuk och ytan fått färg. Servera som ugnsrostad plåträtt.",
        ]
    elif family == "gratäng":
        steps = [
            f"Värm ugnen till 200 grader. Förkoka {carb} tills nästan mjuk; låt rinna av. Bryn proteinråvara som behöver stekas; ägg tillsätts i nästa steg.",
            "Varva kolhydrat, protein, grönsaker och övriga listade ingredienser i en ugnsform. Tillsätt lite vatten så botten inte blir torr; täck formen första halvan av tiden.",
            "Gratinera i ugn 25–35 minuter. Ta av täckningen efter halva tiden; kontrollera att mitten är genomvarm och eventuella ägg har stannat. Låt vila 5 minuter före servering.",
        ]
    elif family == "soppa":
        steps = [
            f"Skär {carb} i små bitar om det är potatis; gryn används enligt förpackningen. Fräs grönsakerna i en stor kastrull.",
            "Tillsätt proteinråvaran, kolhydraten och alla övriga listade ingredienser. Häll på vatten tills det täcker med cirka 2 cm.",
            "Koka upp och sjud som soppa 15–25 minuter, eller tills kolhydraten är helt klar. Späd med vatten till en tydligt skedbar soppa och servera i djupa tallrikar.",
        ]
    elif family in {"gryta", "curry", "chili"}:
        steps = [
            f"Tillaga {carb} separat enligt förpackningen; potatis kokas i bitar 15–20 minuter.",
            "Fräs grönsakerna i kastrull. Tillsätt proteinråvaran och övriga listade ingredienser samt lite vatten så botten täcks.",
            "Låt sjuda utan lock 15–20 minuter till en sammanhållen, tjock gryta. Späd bara vid behov. Servera med den separat tillagade kolhydraten.",
        ]
    elif family == "wrap":
        steps = [
            "Stek proteinråvaran och grönsakerna i lite matolja; ägg rörs till fast äggröra. Värm övriga listade ingredienser med fyllningen.",
            "Värm tortillas hastigt i torr stekpanna. Fördela fyllningen på bröden, vik ihop tortillas runt fyllningen och servera direkt.",
        ]
    elif family == "bowl":
        steps = [
            f"Koka {carb} enligt förpackningen; låt rinna av. Tillaga proteinråvaran i separat panna tills genomlagad; ägg tillagas till fast äggröra.",
            "Tillaga grönsakerna separat så de behåller tuggmotstånd. Värm eventuella listade såsingredienser i liten kastrull.",
            "Håll komponenterna åtskilda: lägg kolhydrat, protein och grönsaker i var sin del av portionsskålarna och lägg eventuell listad sås ovanpå.",
        ]
    elif family == "pasta":
        steps = [
            "Koka pasta enligt förpackningen och spara en kopp kokvatten. Stek proteinråvaran och grönsakerna tills genomlagade.",
            "Värm övriga listade ingredienser med lite pastavatten till en sås. Vänd pastan i såsen tillsammans med protein och grönsaker; eventuella ägg värms under omrörning tills de stannat.",
        ]
    else:
        steps = [
            f"Förbered {carb}: potatis tärnas och kokas nästan mjuk; gryn kokas enligt förpackningen och får rinna av; tortillas skärs i strimlor utan kokning.",
            "Stek proteinråvaran och grönsakerna i en rymlig panna. Ägg rörs till fast äggröra; lägg sedan åt sidan.",
            "Stek kolhydraten separat i pannan så den får stekyta. Vänd ihop med protein, grönsaker och övriga listade ingredienser och värm igenom.",
        ]
    return [prep, protein, *steps, finish]


class DeterministicRecipeCandidateGenerator(RecipeCandidateGenerator):
    """Build normal Swedish weekday candidates without an external LLM."""

    def __init__(self) -> None:
        self._batch_statistics: dict[str, int] = {}

    def generate_reference_candidates(self, *, servings=4):
        """Reviewed cooked weekday recipes for explicit SLV estimates.

        Same Recipe model/optimizer and unrestricted normal product selection.
        The cooking basis checks these exact instructions on edits too.
        """
        from app.services.personal_nutrition import couscous_instructions, reference_instructions

        templates = [
            ("Kokt kyckling med ris och morötter", "plate", "kyckling", "ris", "morot"),
            ("Torsk- och kålsoppa med äggnudlar", "soup", "fisk", "nudlar", "vitkål"),
            ("Pocherad lax med ris och morötter", "plate", "lax", "ris", "morot"),
            ("Kycklingsoppa med äggnudlar och vitkål", "soup", "kyckling", "nudlar", "vitkål"),
            ("Torskgryta med ris och morot", "stew", "fisk", "ris", "morot"),
            ("Lax- och kålsoppa med ris", "soup", "lax", "ris", "vitkål"),
            ("Stekt lax med ris och morötter", "fried_plate", "lax", "ris", "morot"),
            ("Nudelpanna med stekt lax och vitkål", "salmon_pan", "lax", "nudlar", "vitkål"),
            ("Stekt torsk med äggnudlar och vitkål", "cod_pan", "fisk", "nudlar", "vitkål"),
        ]
        recipes = [Recipe(name=name, servings=servings, ingredients=[
            RecipeIngredient(name=protein, quantity=150 * servings, unit="g"),
            RecipeIngredient(name=carb, quantity=80 * servings, unit="g"),
            RecipeIngredient(name=veg, quantity=150 * servings, unit="g"),
        ], instructions=reference_instructions(form))
            for name, form, protein, carb, veg in templates]
        recipes.append(Recipe(
            name="Couscoussallad med tofu och tomat", servings=servings,
            ingredients=[
                RecipeIngredient(name="tofu", quantity=150 * servings, unit="g"),
                RecipeIngredient(name="couscous", quantity=80 * servings, unit="g"),
                RecipeIngredient(name="tomat", quantity=150 * servings, unit="g"),
            ], instructions=couscous_instructions(),
        ))
        return recipes

    def generate_for_meal_type(self, economic_ingredients, meal_type, *, count=80, servings=4):
        """Extend the existing generator with actual breakfast/snack preparations."""
        if meal_type == "dinner":
            return self.generate_candidates(economic_ingredients, count=count, servings=servings)
        from app.models.recipe import RecipeIngredient

        templates = {
            "breakfast": [
                ("Äggsmörgås med tomat", [("bröd", 80, "g"), ("ägg", 2, "st"), ("tomat", 100, "g")],
                 ["Koka äggen, kyl dem och skala.", "Skiva ägg och tomat och lägg på brödet."]),
                ("Ostsmörgås och mjölk", [("bröd", 80, "g"), ("ost", 30, "g"), ("mjölk", 200, "ml")],
                 ["Skiva osten och lägg på brödet.", "Servera med mjölken."]),
                ("Tofumacka med tomat", [("bröd", 80, "g"), ("tofu", 100, "g"), ("tomat", 100, "g")],
                 ["Skiva tofun och stek den i en belagd panna.", "Lägg tofu och skivad tomat på brödet."]),
            ],
            "snack": [
                ("Morotsstavar med ost", [("morot", 100, "g"), ("ost", 25, "g")],
                 ["Skölj och skär moroten i stavar.", "Skär osten i bitar och servera till."]),
                ("Ägg och tomat", [("ägg", 1, "st"), ("tomat", 80, "g")],
                 ["Koka ägget, kyl och skala det.", "Dela tomaten och servera med ägget."]),
                ("Kikärtsröra på bröd", [("kikärtor", 60, "g"), ("bröd", 40, "g"), ("tomat", 60, "g")],
                 ["Mosa de kokta, avrunna kikärtorna.", "Bred på brödet och toppa med hackad tomat."]),
            ],
        }
        if meal_type not in templates:
            raise ValueError("Okänd måltidstyp.")
        return [Recipe(name=name, servings=servings, ingredients=[
            RecipeIngredient(name=n, quantity=q * servings, unit=u)
            for n, q, u in ingredients
        ], instructions=steps) for name, ingredients, steps in templates[meal_type]]

    @property
    def batch_statistics(self) -> dict[str, int]:
        return dict(self._batch_statistics)

    def generate_candidates(
        self,
        economic_ingredients: Iterable[Any] | Any,
        count: int = 80,
        servings: int = 4,
    ) -> list[Recipe]:
        if count < 1 or count > 300:
            raise ValueError("count must be between 1 and 300")
        if servings < 1 or servings > 20:
            raise ValueError("servings must be between 1 and 20")

        pool = _extract_pool(economic_ingredients)
        rows_by_category: dict[IngredientCategory, list[_PoolIngredient]] = defaultdict(list)
        for row in pool:
            rows_by_category[row.entry.category].append(row)

        primaries = [
            *rows_by_category.get(IngredientCategory.LEGUME, []),
            *rows_by_category.get(IngredientCategory.PROTEIN, []),
        ]
        carbohydrates = rows_by_category.get(IngredientCategory.CARBOHYDRATE, [])
        vegetables = rows_by_category.get(IngredientCategory.VEGETABLE, [])
        if not primaries or not carbohydrates or not vegetables:
            raise ValueError(
                "Economic ingredient pool needs a protein/legume, carbohydrate and vegetable"
            )

        # Preserve the selector's economic order even though legumes and other
        # proteins are merged into one structural role.
        primaries.sort(key=lambda row: row.rank)
        buckets: dict[tuple[str, str], list[_CandidateSpec]] = defaultdict(list)
        for primary in primaries:
            for carb_index, carbohydrate in enumerate(carbohydrates):
                for vegetable_index, vegetable in enumerate(vegetables):
                    for family_index, family in enumerate(
                        _families_for(primary, carbohydrate)
                    ):
                        extras = _choose_extras(
                            family,
                            rows_by_category,
                            vegetables,
                            vegetable_index,
                            salt=carb_index + family_index,
                        )
                        ingredients = {
                            primary.canonical,
                            carbohydrate.canonical,
                            vegetable.canonical,
                            *(row.canonical for row in extras),
                        }
                        rank_score = sum(
                            next(row.rank for row in pool if row.canonical == canonical)
                            for canonical in ingredients
                        )
                        buckets[(family, primary.canonical)].append(
                            _CandidateSpec(
                                primary=primary,
                                carbohydrate=carbohydrate,
                                vegetable=vegetable,
                                family=family,
                                extras=extras,
                                rank_score=rank_score,
                            )
                        )

        # First interleave primary ingredients inside each family, then
        # interleave the families themselves.  This makes the candidate set
        # broad enough for diversity constraints without discarding the pool's
        # economic ordering inside each small queue.
        family_queues: dict[str, deque[_CandidateSpec]] = {}
        for family in _FAMILY_ORDER:
            primary_queues: list[deque[_CandidateSpec]] = []
            for primary in primaries:
                specs = sorted(
                    buckets.get((family, primary.canonical), []),
                    key=lambda spec: (
                        spec.rank_score,
                        spec.carbohydrate.rank,
                        spec.vegetable.rank,
                    ),
                )
                if specs:
                    primary_queues.append(deque(specs))
            interleaved: deque[_CandidateSpec] = deque()
            while primary_queues:
                remaining_primary_queues: list[deque[_CandidateSpec]] = []
                for queue in primary_queues:
                    interleaved.append(queue.popleft())
                    if queue:
                        remaining_primary_queues.append(queue)
                primary_queues = remaining_primary_queues
            if interleaved:
                family_queues[family] = interleaved

        recipes: list[Recipe] = []
        self._batch_statistics = {}
        seen_names: set[str] = set()
        seen_profiles: set[frozenset[str]] = set()
        while family_queues and len(recipes) < count:
            remaining_families: dict[str, deque[_CandidateSpec]] = {}
            for family, queue in family_queues.items():
                while queue:
                    spec = queue.popleft()
                    rows = (
                        spec.primary,
                        spec.carbohydrate,
                        spec.vegetable,
                        *spec.extras,
                    )
                    unique_rows = tuple({row.canonical: row for row in rows}.values())
                    profile = frozenset(row.canonical for row in unique_rows)
                    name = _recipe_name(spec)
                    name_key = name.casefold()
                    if profile in seen_profiles or name_key in seen_names:
                        continue
                    seen_profiles.add(profile)
                    seen_names.add(name_key)
                    recipes.append(
                        Recipe(
                            name=name,
                            servings=servings,
                            ingredients=[
                                _make_ingredient(row, servings) for row in unique_rows
                            ],
                            instructions=_instructions(spec, servings),
                        )
                    )
                    self._batch_statistics[spec.family] = (
                        self._batch_statistics.get(spec.family, 0) + 1
                    )
                    break
                if queue:
                    remaining_families[family] = queue
                if len(recipes) == count:
                    break
            family_queues = remaining_families

        if len(recipes) != count:
            raise ValueError(
                f"Could only create {len(recipes)} distinct candidates from this pool; "
                f"requested {count}"
            )
        return recipes


class OpenAIRecipeCandidateGenerator(RecipeCandidateGenerator):
    """Generate structured recipe candidates in bounded OpenAI batches."""

    def __init__(
        self,
        api_key: str | None,
        model: str,
        *,
        batch_size: int = 20,
        client: Any | None = None,
        duplicate_retry_batches: int = 2,
        candidate_batches: Sequence[CandidateBatch] | None = None,
    ) -> None:
        if batch_size < 1 or batch_size > 30:
            raise ValueError("batch_size must be between 1 and 30")
        if duplicate_retry_batches < 0:
            raise ValueError("duplicate_retry_batches cannot be negative")
        if client is None:
            if not api_key:
                raise ValueError("api_key is required when client is not supplied")
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
        self._client = client
        self._model = model
        self._batch_size = batch_size
        self._duplicate_retry_batches = duplicate_retry_batches
        configured_batches = tuple(candidate_batches or DEFAULT_CANDIDATE_BATCHES)
        if not configured_batches:
            raise ValueError("candidate_batches cannot be empty")
        if len({batch.name for batch in configured_batches}) != len(configured_batches):
            raise ValueError("candidate batch names must be unique")
        self._candidate_batches = configured_batches
        self._batch_statistics: dict[str, int] = {}

    @property
    def batch_statistics(self) -> dict[str, int]:
        return dict(self._batch_statistics)

    @staticmethod
    def _serialise_pool(source: Iterable[Any] | Any) -> tuple[str, list[str]]:
        rows = _pool_rows(source)
        payload: list[dict[str, Any]] = []
        canonicals: list[str] = []
        for row in rows:
            if isinstance(row, dict):
                data = dict(row)
            elif hasattr(row, "model_dump"):
                data = row.model_dump(mode="json")
            else:
                canonical = _value(row, "canonical", "canonical_name", "ingredient", "name")
                data = {"canonical": str(canonical or row)}
            canonical = _value(data, "canonical", "canonical_name", "ingredient", "name")
            if canonical:
                resolved = canonicalize_ingredient_name(str(canonical))
                if get_taxonomy_entry(resolved) is not None:
                    canonicals.append(resolved)
            payload.append(data)
        return (
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            list(dict.fromkeys(canonicals)),
        )

    def _generate_batch(
        self,
        *,
        signal: str,
        canonicals: Sequence[str],
        count: int,
        servings: int,
        excluded_names: Sequence[str],
        batch: CandidateBatch,
    ) -> list[Recipe]:
        response = self._client.responses.parse(
            model=self._model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Du skapar strukturerade kandidater till normala svenska "
                        "vardagsmiddagar. Du får aldrig hitta på eller returnera priser, "
                        "butiker, produkter, erbjudanden eller förpackningar."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Skapa exakt {count} distinkta kandidatrecept, vart och ett för "
                        f"exakt {servings} portioner. Varje middag ska ha en protein-, "
                        "baljväxt- eller äggkomponent, en kolhydrat (eller en rejäl "
                        "baljväxtkomponent) och en grönsak. Prioritera den ekonomiska "
                        "råvarupoolen, återanvänd billiga råvaror, håll ingredienslistorna "
                        "korta och undvik specialingredienser. Mängderna ska ge en normal "
                        "middag, ungefär 450–900 kcal, minst 18 g protein och minst 100 g "
                        "grönsaker per portion. Använd bara realistiska "
                        "mängder som kan uttryckas i g, ml eller st. Sätt canonical_name "
                        "på varje ingrediens till ett av de tillåtna canonical-ID:na. "
                        "Anta endast salt, peppar, vatten och neutral matolja hemma; dessa "
                        "ska inte tas med i ingredienslistan. Gör inga prisberäkningar.\n"
                        f"Sökbias för denna batch ({batch.name}): {batch.instruction}\n"
                        "Rättformsbias: fördela kandidaterna så jämnt som möjligt mellan "
                        f"{json.dumps(batch.dish_forms, ensure_ascii=False)}. Använd "
                        "naturliga svenska rättnamn som beskriver maträtten; undvik "
                        "platshållarnamn som 'Risrätt med', 'Nudelrätt med' och "
                        "'Potatisrätt med'.\n"
                        f"Tillåtna canonical-ID:n: {json.dumps(canonicals, ensure_ascii=False)}\n"
                        f"Namn som inte får upprepas: {json.dumps(excluded_names, ensure_ascii=False)}\n"
                        f"Ekonomisk råvarupool (priser är endast signal):\n{signal}"
                    ),
                },
            ],
            text_format=RecipeCollection,
        )
        result = response.output_parsed
        if result is None:
            raise ValueError("OpenAI returned no structured recipe candidates")
        if len(result.recipes) != count:
            raise ValueError(
                f"OpenAI returned {len(result.recipes)} candidates; expected {count}"
            )
        if any(recipe.servings != servings for recipe in result.recipes):
            raise ValueError("OpenAI returned a candidate with the wrong servings")
        return result.recipes

    def generate_candidates(
        self,
        economic_ingredients: Iterable[Any] | Any,
        count: int = 80,
        servings: int = 4,
    ) -> list[Recipe]:
        if count < 1 or count > 300:
            raise ValueError("count must be between 1 and 300")
        if servings < 1 or servings > 20:
            raise ValueError("servings must be between 1 and 20")
        signal, canonicals = self._serialise_pool(economic_ingredients)
        if not canonicals:
            raise ValueError("Economic ingredient pool contains no taxonomy ingredients")

        recipes: list[Recipe] = []
        seen_names: set[str] = set()
        self._batch_statistics = {}
        for batch_config, target in _allocate_candidate_batches(
            count, self._candidate_batches
        ):
            accepted_for_batch = 0
            normal_calls = (target + self._batch_size - 1) // self._batch_size
            attempts_left = normal_calls + self._duplicate_retry_batches
            while accepted_for_batch < target and attempts_left > 0:
                attempts_left -= 1
                requested = min(self._batch_size, target - accepted_for_batch)
                generated_batch = self._generate_batch(
                    signal=signal,
                    canonicals=canonicals,
                    count=requested,
                    servings=servings,
                    excluded_names=[recipe.name for recipe in recipes],
                    batch=batch_config,
                )
                for recipe in generated_batch:
                    key = recipe.name.casefold().strip()
                    if key in seen_names:
                        continue
                    seen_names.add(key)
                    recipes.append(recipe)
                    accepted_for_batch += 1
                self._batch_statistics[batch_config.name] = accepted_for_batch

        if len(recipes) != count:
            raise ValueError(
                f"OpenAI produced only {len(recipes)} distinct candidates; expected {count}"
            )
        return recipes

    def generate_replacement_candidates(
        self,
        current_recipes: Sequence[Recipe],
        cost_feedback: dict[str, Any],
        economic_ingredients: Iterable[Any] | Any,
        count: int = 10,
        servings: int = 4,
    ) -> list[Recipe]:
        """Ask for alternatives, never for a claimed cheaper basket.

        Actual products, package counts, stores and acceptance remain wholly
        deterministic in :class:`MealPlanService`.
        """

        if count < 1 or count > 30:
            raise ValueError("replacement count must be between 1 and 30")
        if servings < 1 or servings > 20:
            raise ValueError("servings must be between 1 and 20")
        signal, canonicals = self._serialise_pool(economic_ingredients)
        if not canonicals:
            raise ValueError("Economic ingredient pool contains no taxonomy ingredients")

        response = self._client.responses.parse(
            model=self._model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "Du föreslår strukturerade ersättningskandidater till en svensk "
                        "veckomeny. Backendens pris- och korgdata är fakta. Du får aldrig "
                        "själv räkna, uppskatta, hitta på eller returnera priser, butiker, "
                        "produkter, erbjudanden eller förpackningar."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Skapa exakt {count} distinkta alternativa middagsrecept, varje "
                        f"för exakt {servings} portioner. De ska kunna ersätta en eller "
                        "två dyra måltider i den nuvarande menyn. Prioritera råvaror i "
                        "den ekonomiska poolen, korta ingredienslistor och delade "
                        "råvaror/förpackningar. Varje rätt måste innehålla en protein-, "
                        "baljväxt- eller äggkomponent, en kolhydrat (eller rejäl "
                        "baljväxtkomponent) och en grönsak. Använd realistiska mängder i "
                        "g, ml eller st. Varje middag ska ungefär ge 450–900 kcal, minst "
                        "18 g protein och minst 100 g grönsaker per portion. Sätt "
                        "canonical_name till ett tillåtet ID. Anta "
                        "bara salt, peppar, vatten och neutral matolja hemma. Returnera "
                        "inga priser och påstå inte att något är billigare; backend "
                        "avgör detta efter faktisk omräkning.\n"
                        "Nuvarande recept:\n"
                        + json.dumps(
                            [
                                recipe.model_dump(mode="json")
                                for recipe in current_recipes
                            ],
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        + "\nDeterministisk kostnadsfeedback (endast signal):\n"
                        + json.dumps(
                            cost_feedback,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                        + "\nTillåtna canonical-ID:n:\n"
                        + json.dumps(canonicals, ensure_ascii=False)
                        + "\nEkonomisk råvarupool (priser är endast signal):\n"
                        + signal
                    ),
                },
            ],
            text_format=RecipeCollection,
        )
        result = response.output_parsed
        if result is None:
            raise ValueError("OpenAI returned no structured replacement candidates")
        if len(result.recipes) != count:
            raise ValueError(
                f"OpenAI returned {len(result.recipes)} replacements; expected {count}"
            )
        if any(recipe.servings != servings for recipe in result.recipes):
            raise ValueError("OpenAI returned a replacement with the wrong servings")
        if len({recipe.name.casefold().strip() for recipe in result.recipes}) != count:
            raise ValueError("OpenAI returned duplicate replacement names")
        return result.recipes


def create_recipe_candidate_generator(
    *,
    openai_api_key: str | None = None,
    openai_model: str = "gpt-5.4-mini",
    batch_size: int = 20,
) -> RecipeCandidateGenerator:
    """Choose the LLM implementation only when credentials are configured."""

    if openai_api_key:
        return OpenAIRecipeCandidateGenerator(
            openai_api_key,
            openai_model,
            batch_size=batch_size,
        )
    return DeterministicRecipeCandidateGenerator()


__all__ = [
    "DEFAULT_CANDIDATE_BATCHES",
    "CandidateBatch",
    "DeterministicRecipeCandidateGenerator",
    "OpenAIRecipeCandidateGenerator",
    "RecipeCandidateGenerator",
    "create_recipe_candidate_generator",
]
