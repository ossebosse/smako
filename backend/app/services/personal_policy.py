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
        "message": "Granska och redigera. Det du vill undvika tas bort ur recept och varor; ange allergi separat.",
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


# Whole words (after search_text) that mark a household item as not being food.
# /personal and the trial interfaces mark own items with the same words;
# test_own_item_nonfood_words keeps the three lists in step.
NONFOOD_WORDS = frozenset({
    "servett", "servetter", "toalettpapper", "hushallspapper", "diskmedel", "tvattsvamp",
    "diskborste", "diskborstar", "bakplatspapper", "avfallspasar", "avfallspase", "soppasar", "soppase",
    "blojor", "byxblojor", "bloja", "byxbloja",
    "tvattmedel", "skoljmedel", "tandkram", "tandborste", "tandborstar", "eltandborste",
    "schampo", "shampoo", "tval", "handtval", "aluminiumfolie", "plastfolie", "folie",
    "plastpasar", "plastpase", "fryspasar", "fryspase",
    "batteri", "batterier", "tandstickor", "vatservett", "vatservetter", "binda", "bindor",
    "tampong", "tamponger", "deodorant", "rakblad", "disktablett", "disktabletter",
    "kattmat", "hundmat", "kattsand",
})


def is_nonfood(name):
    return bool(set(search_text(name).split()) & NONFOOD_WORDS)


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


# Compound words name what they are made of: "rödlök" is a lök, "fläskfilé" is
# fläsk, "prästost" is an ost. A term matches a whole word, the end of a word or
# the start of a word, except listed words that only look like a compound.
_NOT_COMPOUNDS = {"ost": frozenset({"ostron"})}


def mentions(term, text):
    """Whether a name or declaration names the term, also inside a compound word."""
    wanted = search_text(term)
    if not wanted:
        return False
    if " " in wanted:
        return f" {wanted} " in f" {search_text(text)} "
    words = search_text(text).split()
    for i, word in enumerate(words):
        # "glutenfri", "laktosfritt" and "utan ägg" say the opposite.
        if (i and words[i - 1] == "utan") or word.endswith(("fri", "fria", "fritt")):
            continue
        if word == wanted:
            return True
        # The other part of a compound is a word of its own, at least three letters ("pris" is not ris).
        rest = len(word) - len(wanted)
        if len(wanted) >= 3 and rest >= 3 and (word.endswith(wanted) or word.startswith(wanted)) and word not in _NOT_COMPOUNDS.get(wanted, ()):
            return True
    return False


# Owner decision 2026-11-14 (docs/PLANNING-ARCHITECTURE.md). Words and source
# categories that mark a composite product, where something the person avoids
# can be hidden without showing in the name.
_COMPOSITE_STEMS = (
    "sas", "dressing", "buljong", "fond", "marinad", "krydd", "mix", "blandning", "fardig", "pizza",
    "paj", "pirog", "soppa", "gryta", "wok", "pesto", "rora", "dipp", "pastej", "korv", "kottbull",
    "biff", "burgare", "schnitzel", "nugget", "panerad", "chips", "snacks", "godis", "kaka", "kakor",
    "kex", "brod", "bulle", "bullar", "glass", "choklad", "musli", "granola", "flingor", "smaksatt",
    "nudlar", "pastasas", "curry", "salsa", "majonnas", "ketchup", "senap", "sylt", "mos", "fyllning",
)
_COMPOSITE_WORDS = frozenset({"dip", "bas", "kit"})
_COMPOSITE_CATEGORIES = ("fardigmat", "godis", "snacks", "brod", "glass", "palagg", "sas", "dressing",
                         "smaksattare", "delikatess", "barn", "kiosk")


def is_composite(product):
    words = search_text(f"{product.name} {getattr(product, 'canonical_name', '') or ''}").split()
    if any(w in _COMPOSITE_WORDS or w.endswith("bas") and len(w) > 4 or any(stem in w for stem in _COMPOSITE_STEMS) for w in words):
        return True
    category = search_text(getattr(product, "category", "") or "")
    return any(stem in category for stem in _COMPOSITE_CATEGORIES)


# Fresh fruit, vegetables, mushrooms and herbs need no ingredient list under EU
# 1169/2011 article 19: the product is its own single ingredient. Products whose
# name points at one of the major allergens stay with the declaration rule.
_PRODUCE_CATEGORIES = ("frukt gront", "frukt och gront", "frukt gront")
_PRODUCE_NOT_SINGLE = (
    "mix", "blandning", "rora", "juice", "smoothie", "torkad", "torkade", "inlagd", "inlagda", "marinerad",
    "sas", "dressing", "soppa", "wok", "pesto", "chips", "snacks", "dipp", "kit", "fardig", "sallad mix",
    "not", "mandel", "cashew", "pistage", "sesam", "senap", "soja", "edamame", "selleri", "lupin", "vete",
    "fron", "karnor", "russin", "dadlar", "fikon", "aprikoser", "krutong",
)


def single_ingredient_by_rule(product):
    """A fresh produce item that is its own and only ingredient."""
    category = search_text(getattr(product, "category", "") or "")
    if not any(category.startswith(c) for c in _PRODUCE_CATEGORIES):
        return False
    name = search_text(product.name)
    return not any(stem in name for stem in _PRODUCE_NOT_SINGLE)


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
        if _contains(term, (product.name, product.canonical_name)) or mentions(term, product.name) or mentions(term, product.canonical_name) or (
            search_text(term) == "fisk" and getattr(product, "food_family", None) == "fish"
        ):
            raise PolicyConflict(f"{product.name} innehåller något du har valt bort: {term}.")
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
                        f"{product.name}: produktdeklarationen anger {term}, som du har valt bort."
                    )
        unknown = [a for a in profile.allergies if a not in ALLERGENS]
        if unknown:
            raise PolicyConflict(
                "Allergin kan inte verifieras: " + ", ".join(unknown),
                stage="policy_taste",
                code="DATA_BLOCKED",
            )
        complete = not (
            facts is None
            or not facts.ingredients_complete
            or set(facts.conflicts) & {"ingredients", "identity_variant"}
        )
        # Owner decision 2026-11-14: without a complete declaration, Ät inte
        # is checked on the name, and only composite products need the
        # declaration; an allergy accepts only fresh produce that is its own
        # single ingredient. Everything else still fails closed.
        if not complete and (single_ingredient_by_rule(product) or (not profile.allergies and not is_composite(product))):
            hard = []
        elif not complete:
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
        for term in (profile.exclusions if hard else ()):
            if _contains(term, ingredient_composition(facts.ingredients)):
                raise PolicyConflict(f"{product.name} innehåller utesluten ingrediens: {term}.")
        for term in (profile.allergies if hard else ()):
            allergen = ALLERGENS[term]
            if allergen in facts.allergens_present or allergen in facts.allergens_trace:
                raise PolicyConflict(f"{product.name}: innehåller eller kan innehålla spår av {allergen}.")
            if allergen not in facts.allergens_checked:
                raise PolicyConflict(
                    f"{product.name}: {allergen} framgår inte av innehållsförteckningen.",
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
                f"{product.name}: vi vet inte om varan är ekologisk eller innehåller animalier.",
                stage="organic",
                code="DATA_BLOCKED",
            )
        if facts.animal and facts.organic is not True:
            raise PolicyConflict(
                f"{product.name} är inte märkt som ekologisk.",
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


def protein_category(recipe):
    from app.services.diet_policy import (
        FINFISH_INGREDIENTS,
        POULTRY_INGREDIENTS,
        SHELLFISH_INGREDIENTS,
    )

    # Each recipe receives ONE category. Mixed meat/fish recipes do not count twice.
    names = [canonicalize_ingredient_name(i.name) for i in recipe.ingredients]
    main = primary_ingredient(recipe)
    if main in POULTRY_INGREDIENTS:
        return "chicken"
    if main in FINFISH_INGREDIENTS:
        return "fish"
    if main in SHELLFISH_INGREDIENTS:
        return "shellfish"
    if not recipe_respects_diet(recipe, preference="vegetarian"):
        if any(n in POULTRY_INGREDIENTS for n in names):
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
