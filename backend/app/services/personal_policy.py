"""Deterministic personal constraints, with explicit evidence gaps.

Retained catalog evidence supplies a subset of these facts. Missing evidence
remains unknown; caller-supplied recipes can never certify product facts.
No generated narrative, product name or brand is ecological/nutrition evidence.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from app.models.personal import TasteProfile
from app.services.diet_policy import ingredient_is_excluded, recipe_respects_diet
from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.product_search import search_text
from app.services.recipe_profile import primary_ingredient


class PolicyConflict(ValueError):
    def __init__(self, message, *, code="CONFLICT", conflicts=None, stage=None, diagnostics=None):
        super().__init__(message)
        self.code = code
        self.conflicts = conflicts or [message]
        self.stage = stage
        self.diagnostics = diagnostics


@dataclass(frozen=True)
class ProductFacts:
    source: str
    source_product_id: str
    source_snapshot_id: str
    retailer_product_id: str | None = None
    product_classification: tuple[str, ...] = ()
    ingredients_complete: bool = False
    ingredient_evidence_kind: str | None = None
    ingredients: tuple[str, ...] = ()
    allergens_checked: tuple[str, ...] = ()
    allergens_present: tuple[str, ...] = ()
    allergens_trace: tuple[str, ...] = ()
    organic: bool | None = None
    animal: bool | None = None
    # Per 100 g/ml of the actual purchased ingredient, NOT cooked recipe weight.
    nutrition_unit: str | None = None
    nutrition_basis: str | None = None
    nutrition_preparation: str = "as_sold"
    nutrition: dict[str, float] = field(default_factory=dict)
    observed_at: str | None = None
    field_sources: dict[str, tuple[dict, ...]] = field(default_factory=dict)
    conflicts: tuple[str, ...] = ()


ALLERGENS = {
    "jordnöt": "jordnötter",
    "jordnötter": "jordnötter",
    "mjölk": "mjölk",
    "ägg": "ägg",
    "fisk": "fisk",
    "skaldjur": "skaldjur",
    "gluten": "gluten",
    "vete": "vete",
    "soja": "soja",
    "sesam": "sesam",
    "nötter": "nötter",
    "selleri": "selleri",
    "senap": "senap",
    "lupin": "lupin",
    "sulfit": "sulfit",
    "blötdjur": "blötdjur",
}


def merged_profile(base, override):
    return TasteProfile(
        **{
            k: list(dict.fromkeys(getattr(base, k) + getattr(override, k)))
            for k in ("likes", "dislikes", "exclusions", "allergies")
        }
    )


def interpret_profile(text):
    if not isinstance(text, str) or len(text) > 2000:
        raise ValueError("Beskrivningen får vara högst 2 000 tecken.")
    result = {k: [] for k in ("likes", "dislikes", "exclusions", "allergies")}
    unresolved = []
    # Rules intentionally demand explicit language. Unparsed text stays visible.
    for part in re.split(
        r"[,;\n.]|\boch\b(?=\s*(?:gillar|ogillar|föredrar|undvik|allerg))",
        text,
        flags=re.IGNORECASE,
    ):
        part = part.strip()
        if not part:
            continue
        match = re.fullmatch(
            r"(gillar|föredrar|ogillar|allergisk mot|allergi mot|måste undvika|uteslut|undvik)\s+(.+)",
            part,
            re.IGNORECASE,
        )
        if not match:
            unresolved.append(part)
            continue
        command, value = match.groups()
        key = {
            "gillar": "likes",
            "föredrar": "likes",
            "ogillar": "dislikes",
            "allergisk mot": "allergies",
            "allergi mot": "allergies",
            "måste undvika": "exclusions",
            "uteslut": "exclusions",
            "undvik": "exclusions",
        }[command.casefold()]
        result[key].extend(v.strip() for v in re.split(r"\boch\b", value) if v.strip())
    profile = TasteProfile(**result)
    return {
        "profile": profile.model_dump(),
        "unresolved": unresolved,
        "message": "Granska och redigera. Måste undvika är en hård uteslutning; ange allergi separat.",
    }


def interpretation(query):
    return [
        f"{float(p.replace(',', '.')):g} %".replace(".", ",")
        for p in re.findall(r"(\d+(?:[.,]\d+)?)\s*%", query)
    ]


def properties_match(product, properties):
    for prop in properties:
        if prop.endswith("%"):
            wanted = float(prop.rstrip("% ").replace(",", "."))
            values = [
                float(v.replace(",", "."))
                for v in re.findall(r"(\d+(?:[.,]\d+)?)\s*%", product.name)
            ]
            if wanted not in values:
                return False
        elif not set(search_text(prop).split()) <= set(search_text(product.name).split()):
            return False
    return True


def is_nonfood(name):
    return bool(
        set(search_text(name).split())
        & {
            "servett",
            "servetter",
            "toalettpapper",
            "hushallspapper",
            "diskmedel",
            "tvattsvamp",
            "diskborste",
            "bakplatspapper",
            "avfallspasar",
            "soppasar",
            "blojor",
            "byxblojor",
            "bloja",
            "byxbloja",
        }
    )


def _contains(term, names):
    token = search_text(term)
    for name in names:
        words = search_text(name).split()
        if token == search_text(name) or token in words:
            return True
        if token == "fisk" and any(ingredient_is_excluded(n, ["fisk"]) for n in [name, *words]):
            return True
        if token == "fisk" and re.search(
            r"\b(?:fisk(?:sås|sas|buljong|fond|extrakt|gelatin|olja|protein)?|fish(?:\s+sauce)?|"
            r"ansjovis\w*|anchov\w*|sardell\w*|sardin\w*|bonito\w*|katsuobushi|surimi|lax\w*|tonfisk\w*)\b",
            search_text(name),
        ):
            return True
    return False


def ingredient_composition(declarations):
    """A precautionary trace statement is distinct from ingredient occurrence."""
    return tuple(
        re.split(r"kan innehålla|spår av|may contain", value, maxsplit=1, flags=re.IGNORECASE)[0]
        for value in declarations
    )


def check_product(product, profile, facts=None, *, organic_animals=False):
    if is_nonfood(product.name):
        return
    hard = profile.exclusions + profile.allergies
    # A positive conflict needs no claim about the completeness of other data.
    for term in hard:
        if _contains(term, (product.name, product.canonical_name)) or (
            search_text(term) == "fisk" and getattr(product, "food_family", None) == "fish"
        ):
            raise PolicyConflict(f"{product.name} strider mot ditt hårda val: {term}.")
    if hard:
        if facts and facts.ingredients:
            for term in hard:
                names = (
                    facts.ingredients
                    if term in profile.allergies
                    else ingredient_composition(facts.ingredients)
                )
                if _contains(term, names):
                    raise PolicyConflict(
                        f"{product.name}: produktdeklarationen anger {term}, som strider mot ditt hårda val."
                    )
        unknown = [a for a in profile.allergies if a not in ALLERGENS]
        if unknown:
            raise PolicyConflict(
                "Allergin kan inte verifieras: " + ", ".join(unknown),
                stage="policy_taste",
                code="DATA_BLOCKED",
            )
        if (
            facts is None
            or not facts.ingredients_complete
            or set(facts.conflicts) & {"ingredients", "identity_variant"}
        ):
            missing = (
                "fullständig spårbar ingrediens-/allergeninformation"
                if profile.allergies
                else "tillräckligt spårbart ingrediensunderlag"
            )
            raise PolicyConflict(
                f"{product.name}: {missing} saknas.",
                stage="policy_taste",
                code="DATA_BLOCKED",
            )
        for term in profile.exclusions:
            if _contains(term, ingredient_composition(facts.ingredients)):
                raise PolicyConflict(f"{product.name} innehåller utesluten ingrediens: {term}.")
        for term in profile.allergies:
            allergen = ALLERGENS[term]
            if allergen in facts.allergens_present or allergen in facts.allergens_trace:
                raise PolicyConflict(f"{product.name}: deklarerad förekomst/spår av {allergen}.")
            if allergen not in facts.allergens_checked:
                raise PolicyConflict(
                    f"{product.name}: {allergen} är inte verifierat i källan.",
                    stage="policy_taste",
                    code="DATA_BLOCKED",
                )
    if organic_animals:
        # (animal -> organic) is satisfied by verified organic status even
        # when animal classification is unknown. No animal absence is claimed.
        if facts and facts.organic is True:
            return
        if facts is None or facts.animal is None:
            raise PolicyConflict(
                f"{product.name}: animaliskt innehåll/ekostatus kan inte verifieras.",
                stage="organic",
                code="DATA_BLOCKED",
            )
        if facts.animal and facts.organic is not True:
            raise PolicyConflict(
                f"{product.name} saknar verifierad ekologisk status för animalier.",
                stage="organic",
                code="DATA_BLOCKED" if facts.organic is None else "CONFLICT",
            )


def pantry_checks(items, profile):
    """Inventory may record conflicting food, but never certify it as safe."""
    from types import SimpleNamespace

    results = []
    for item in items:
        if not (profile.allergies or profile.exclusions) or item["unusable"]:
            continue
        try:
            check_product(SimpleNamespace(name=item["name"], canonical_name=item["name"]), profile)
        except PolicyConflict as exc:
            results.append({"item_id": item["id"], "code": exc.code, "message": str(exc)})
    return results


FINFISH_INGREDIENTS = frozenset({"fisk", "lax", "torsk", "tonfisk", "makrill", "rökt makrill",
                                "sardiner", "matjessill", "stenbitsrom", "rökt lax", "varmrökt lax"})
SHELLFISH_INGREDIENTS = frozenset({"räkor", "råa räkor", "skaldjur", "musslor", "bläckfisk"})


def protein_category(recipe):
    # Each recipe receives ONE category. Mixed meat/fish recipes do not count twice.
    names = [canonicalize_ingredient_name(i.name) for i in recipe.ingredients]
    main = primary_ingredient(recipe)
    if main in {"kyckling", "kalkon"}:
        return "chicken"
    if main in FINFISH_INGREDIENTS:
        return "fish"
    if main in SHELLFISH_INGREDIENTS:
        return "shellfish"
    if not recipe_respects_diet(recipe, preference="vegetarian"):
        if any(n in {"kyckling", "kalkon"} for n in names):
            return "chicken"
        if any(n in FINFISH_INGREDIENTS for n in names):
            return "fish"
        if any(n in SHELLFISH_INGREDIENTS for n in names):
            return "shellfish"
        return "meat"
    return "vegetarian"


def remaining_category_capacity(meal, fixed_slots=(), *, classify=protein_category):
    """Safe per-category capacity for a new choice, including fixed swap peers.

    Unspecified categories share the unassigned places; explicit zero is a ban.
    This is only a necessary condition, never proof that a menu is feasible.
    """
    # Shellfish may occupy an unassigned place, never an explicit fish quota.
    # The public four-category request vocabulary is unchanged.
    categories = ("vegetarian", "chicken", "fish", "meat", "shellfish")
    chosen = [s.recipe for s in fixed_slots if s.meal_type == meal.meal_type and s.recipe]
    counts = Counter(classify(r) for r in chosen)
    remaining = meal.count - len(chosen)
    if remaining <= 0 or any(counts[k] > n for k, n in meal.distribution.items()):
        return dict.fromkeys(categories, 0)
    required = {k: n - counts[k] for k, n in meal.distribution.items()}
    unassigned = remaining - sum(required.values())
    if unassigned < 0:
        return dict.fromkeys(categories, 0)
    return {k: required.get(k, unassigned) for k in categories}


def distribution_ok(slots, meals, *, partial=False, classify=protein_category):
    for meal in meals:
        chosen = [s.recipe for s in slots if s.meal_type == meal.meal_type and s.recipe]
        counts = Counter(classify(r) for r in chosen)
        remaining = meal.count - len(chosen)
        for kind, number in meal.distribution.items():
            if counts[kind] > number or counts[kind] + remaining < number:
                return False
            if not partial and counts[kind] != number:
                return False
    return True


def preference_score(recipes, profile):
    names = [i.name for r in recipes for i in r.ingredients]
    return sum(_contains(v, names) for v in profile.dislikes) - sum(
        _contains(v, names) for v in profile.likes
    )
