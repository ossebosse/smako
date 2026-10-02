"""Measured edible input method for explicitly designed recipes.

This is a macro estimate per portion, not a retention model. All specified food
and juices are served. Added water may evaporate: no cooked mass is inferred.
The recipe design and ingredient form must validate independently of nutrition.
Original recipes remain immutable; adaptations record their full content hash.
"""

import hashlib
import json
import re
from dataclasses import replace

from app.models.recipe import Recipe, RecipeIngredient, RecipePreparation
from app.services.ingredient_normalizer import canonicalize_ingredient_name as canonical

VERSION = "smako-edible-input-v1"
# Culinary design choices in ml per serving, NOT measured oil uptake or yield.
# A small measured saute base for wet dishes; more for oven/pan surface coverage.
OIL = {
    **dict.fromkeys(("gryta", "pasta", "chili", "curry", "gratäng", "soppa", "bowl", "wrap"), 5),
    "ugn": 7.5,
    **dict.fromkeys(("wok", "panna", "risrätt", "nudelrätt", "potatisrätt", "husman"), 10),
    "tofu_toast": 5,
    "egg_toast": 5,
    "egg_tomato": 5,
    "chickpea_toast": 0,
    "cheese_toast": 0,
}
DRY = {"pasta", "ris", "nudlar", "couscous", "linser"}
DRAINED = {"kikärtor", "svarta bönor", "kidneybönor", "bönor"}
RAW = {
    "potatis",
    "morot",
    "vitkål",
    "gul lök",
    "rödlök",
    "vitlök",
    "tomat",
    "broccoli",
    "kyckling",
    "fläskkött",
    "lax",
    "fisk",
    "nötfärs",
    "blandfärs",
    "ägg",
}


def content_hash(recipe):
    value = recipe.model_dump(mode="json", exclude={"preparation"})
    for item in value["ingredients"]:
        item.pop("canonical_name", None)
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def instructions(family, forms, servings):
    if family not in OIL:
        raise ValueError("Unsupported preparation family")
    steps = [
        f"Mät upp ingredienslistans använda mängder för {servings} portioner. Gram avser ätbar insats efter att skal, ben eller andra oätliga delar tagits bort; ml avser uppmätt volym. Förpackningsrest ingår inte. Köp tillräckligt för dessa ätbara minimimängder och kontrollväg efter putsning; ingen ätbar andel eller densitet antas.",
        "Använd exakt de angivna ingrediensformerna: "
        + "; ".join(f"{n}: {f}" for n, f in sorted(forms.items()))
        + ".",
    ]
    if any(f == "dry" for f in forms.values()):
        steps.append(
            "Tillaga torra gryn och röda linser helt mjuka med vatten enligt förpackningen, med absorptionsmetod. Koka pasta och nudlar direkt i rättens vätska med lite vatten i taget. Ingen kokvätska hälls bort. Använd inte färdigkokta varor som ersättning för torr mängd."
        )
    if "cooked_drained" in forms.values():
        steps.append(
            "Använd färdigkokta baljväxter. Väg efter avrinning enligt listan; använd bara produkt med belagd avrunnen förpackningsmängd och näringsgrund för avrunnen vara. Ingen torr-till-kokt omräkning ingår."
        )
    if "ägg" in forms:
        steps.append(
            "Knäck ägg och väg upp rå ätbar äggmassa utan skal enligt listan. Antal ägg är inte omräknat till gram. Vispa och tillaga till fast äggröra; servera all uppmätt äggmassa."
        )
    if family == "ugn":
        steps.append(
            "Värm ugnen till 200 grader. Skär råvarorna i jämna mindre bitar och lägg i täckt ugnsform med den uppmätta rapsoljan och lite vatten. Baka tills råvarorna är helt genomlagade och potatisen mjuk. Behåll och servera all genomhettad sky."
        )
    elif family == "gratäng":
        steps.append(
            "Värm ugnen till 200 grader. Tillaga torra ingredienser med absorptionsmetoden ovan. Värm övriga råvaror med den uppmätta rapsoljan, lägg allt i täckt ugnsform och gratinera tills genomlagat. Behåll all vätska i rätten."
        )
    elif family in {"gryta", "chili", "curry", "soppa"}:
        steps.append(
            "Fräs grönsakerna varsamt i den uppmätta rapsoljan. Tillsätt övriga ingredienser och vatten efter behov. Sjud tills råvarorna är genomlagade; servera all mat och vätska som gryta eller soppa."
        )
    elif family == "chickpea_toast":
        steps.append(
            "Mosa de uppmätta kokta avrunna kikärtorna. Bred på brödet och toppa med uppmätt tomat. Ingen olja tillsätts."
        )
    elif family == "cheese_toast":
        steps.append(
            "Lägg den uppmätta hårdosten på brödet i en ugnsform. Värm i ugn vid 200 grader tills osten smält och smörgåsen är varm. Servera även ost och fett som hamnat i formen; ingen olja eller annan ingrediens tillsätts."
        )
    else:
        steps.append(
            "Tillaga råvaror som behöver värmas varsamt i en belagd panna med den uppmätta rapsoljan. Tillsätt lite vatten om det fastnar. Vänd ned tillagade gryn om de ingår; servera bröd eller tortillas vid sidan. Behåll all mat och skrapa ned all sky och olja i portionerna."
        )
    steps.append(
        "Fördela all uppmätt mat, olja och vätska jämnt mellan portionerna. Inga olistade ingredienser ingår; tillsätt endast dricksvatten. Vattenupptag och avdunstning är inte uppmätta. Näringen är en insatsbaserad uppskattning per portion, inte per 100 g färdig rätt."
    )
    return steps


def adapt(recipe, family, *, origin="smako_recipe_design"):
    """Create a separate version; never reinterpret an old recipe in place."""
    if family not in OIL:
        raise ValueError("Unknown recipe family")
    ingredients = []
    forms = {}
    for item in recipe.ingredients:
        name = canonical(item.name)
        if name == "rapsolja":
            raise ValueError("Adapt an original recipe, not an already adapted version")
        if name == "ägg" and item.unit == "st":
            # New portion design: 100 g for a meal, 50 g for the snack.
            # This is not an asserted conversion of the former egg count.
            item = item.model_copy(
                update={
                    "quantity": (50 if family == "egg_tomato" else 100) * recipe.servings,
                    "unit": "g",
                }
            )
        if name == "crème fraiche" and item.unit == "ml":
            # New recipe design: weigh the same numerical serving in grams.
            # Thick cultured cream is measured by mass; this is NOT density.
            item = item.model_copy(update={"unit": "g"})
        if name == "tortillas" and item.unit == "st":
            item = item.model_copy(update={"quantity": 100 * recipe.servings, "unit": "g"})
        if item.unit not in {"g", "ml"}:
            raise ValueError(f"Unresolved recipe input unit: {item.name}/{item.unit}")
        ingredients.append(item)
        forms[name] = (
            "dry"
            if name in DRY
            else "cooked_drained"
            if name in DRAINED
            else "raw_edible"
            if name in RAW
            else "as_sold"
        )
    if OIL[family]:
        ingredients.append(
            RecipeIngredient(
                name="rapsolja",
                canonical_name="rapsolja",
                quantity=OIL[family] * recipe.servings,
                unit="ml",
            )
        )
        forms["rapsolja"] = "as_sold"
    result = Recipe(
        name=recipe.name,
        servings=recipe.servings,
        ingredients=ingredients,
        instructions=instructions(family, forms, recipe.servings),
        preparation=RecipePreparation(
            version=VERSION,
            origin=origin,
            parent_sha256=content_hash(recipe),
            family=family,
            input_forms=forms,
        ),
    )
    validate(result)
    return result


def validate(recipe):
    if getattr(recipe, "design", None) is not None:
        from app.services.recipe_library import validate_recipe_design
        validate_recipe_design(recipe)
        return True
    p = recipe.preparation
    if p is None:
        return False
    names = [canonical(i.name) for i in recipe.ingredients]
    if len(set(names)) != len(names) or set(names) != set(p.input_forms):
        raise ValueError("Preparation operands differ from recipe ingredients")
    special_operands = {
        "chickpea_toast": {"kikärtor", "bröd", "tomat"},
        "cheese_toast": {"ost", "bröd"},
        "egg_toast": {"ägg", "bröd", "tomat", "rapsolja"},
        "egg_tomato": {"ägg", "tomat", "rapsolja"},
        "tofu_toast": {"tofu", "bröd", "tomat", "rapsolja"},
    }
    if p.family in special_operands and set(names) != special_operands[p.family]:
        raise ValueError("Recipe ingredients do not match the preparation operations")
    if recipe.instructions != instructions(p.family, p.input_forms, recipe.servings):
        raise ValueError("Preparation instructions changed; calculation method no longer applies")
    for i in recipe.ingredients:
        name = canonical(i.name)
        expected = (
            "dry"
            if name in DRY
            else "cooked_drained"
            if name in DRAINED
            else "raw_edible"
            if name in RAW
            else "as_sold"
        )
        if i.unit not in {"g", "ml"} or p.input_forms[name] != expected:
            raise ValueError("Unsupported ingredient form/unit")
        if name in DRY | DRAINED | RAW and i.unit != "g":
            raise ValueError("Edible solid input must be weighed, not inferred from pieces/ml")
    oil = next((i for i in recipe.ingredients if canonical(i.name) == "rapsolja"), None)
    if OIL[p.family] and (
        oil is None
        or oil.unit != "ml"
        or abs(oil.quantity - OIL[p.family] * recipe.servings) > 1e-6
    ):
        raise ValueError("Missing or inconsistent designed oil quantity")
    return True


def basis(recipe):
    if not validate(recipe):
        return None
    from app.services.reviewed_warm_meals import SOURCES

    return {
        "sources": SOURCES,
        "version": VERSION,
        "method": "measured_edible_input_sum_per_portion",
        "origin": recipe.preparation.origin,
        "parent_sha256": recipe.preparation.parent_sha256,
        "family": recipe.preparation.family,
        "input_forms": recipe.preparation.input_forms,
        "description": "Receptutformning: summera deklarerad eller tillåten referensbaserad näring från använda ätbara insatser och dela med portioner. All mat, olja och sky ska serveras. Uppskattning, inte uppmätt retention.",
        "cooked_weight": "NOT_VERIFIED",
        "per_100g_cooked": "NOT_AVAILABLE",
        "retention_factors": "NOT_MEASURED",
        "edible_purchase_yield": "NOT_ASSUMED",
        "purchase_reservation": "Kontrollväg ätbar mängd efter putsning; angiven receptmängd är nödvändig ätbar minimimängd, inte belagd bruttovikt.",
    }


def input_evidence(recipe, product, name, unit, qualified, fact):
    """Preserve identity, units, source values and opt-in at the caller."""
    from app.services.nutrition_reference import product_reference, reference_evidence

    if not validate(recipe):
        return None
    form = recipe.preparation.input_forms.get(canonical(name))
    if not form or unit not in {"g", "ml"} or (fact and fact.conflicts):
        return None
    text = product.name.casefold()
    composition = " ".join(fact.ingredients).casefold() if fact else ""
    if canonical(name) == "ägg" and form == "raw_edible":
        # Carton weight includes shell; even a source-stated 636 g/12-pack
        # cannot certify 636 edible grams. Do not invent an egg/shell factor.
        # Liquid whole egg is a separate directly measurable purchased form.
        liquid_whole = "flytande" in text and "hela ägg" in text and "äggvita" not in text
        edible_mass = bool(
            fact
            and any(
                (e.get("basis") == "edible_as_sold" or (
                    e.get("basis") == "estimated_edible" and product.quantity_confidence == "estimated"
                ))
                and e.get("unit") == "g"
                and e.get("quantity") == product.usable_quantity
                and e.get("source")
                for e in fact.field_sources.get("usable_quantity", ())
            )
        )
        if not liquid_whole and not edible_mass:
            return None
    if form == "dry" and (re.search(r"kokt|färdig|konserv|avrun", text) or "vatten" in composition):
        return None
    if form == "raw_edible" and re.search(r"kokt|grillad|stekt|panerad|rökt|gravad|gravlax|rimmad", text):
        return None
    if (
        form == "raw_edible"
        and canonical(name) in {"tomat", "potatis", "vitlök"}
        and product_reference(product, name, fact) is None
    ):
        # A correct composite/dried declaration is not a raw-food declaration.
        # Reuse the established fresh/juice/puree/canned identity boundary even
        # when all requested nutrient fields happen to be available.
        return None
    if form == "cooked_drained":
        # The existing usable_quantity drives whole-package purchase planning.
        # It must explicitly refer to source-proven drained contents. A small
        # package number, a bean name or a generic reference is not that proof.
        if not (
            fact
            and fact.nutrition_preparation in {"cooked_drained", "draining_unspecified"}
            and unit == "g"
            and fact.nutrition_unit == "g"
            and any(
                e.get("basis") == "drained"
                and e.get("unit") == "g"
                and e.get("quantity") == product.usable_quantity
                and e.get("source")
                for e in fact.field_sources.get("usable_quantity", ())
            )
        ):
            return None
        qualified = bool(fact.nutrition and fact.nutrition_basis and fact.nutrition_preparation == "cooked_drained")
    evidence = fact if qualified else None
    if evidence is None:
        if unit != "g" or (fact and fact.nutrition and not (
            form == "cooked_drained" and fact.nutrition_preparation == "draining_unspecified"
        )):
            return None
        if form == "cooked_drained":
            words = set(re.findall(r"[a-zåäö0-9]+", composition))
            common = {'ingredienser', 'ekologiska', 'kokta', 'vatten', 'salt',
                      'antioxidationsmedel', 'e300', 'askorbinsyra'}
            rules = {'kikärtor': (3815, {'kikärtor', 'kikärter'}),
                     'kidneybönor': (3816, {'kidneybönor'}),
                     'svarta bönor': (3817, {'svarta', 'bönor'}),
                     'bönor': (3761, {'stora', 'vita', 'bönor'})}
            identity, food_words = rules.get(canonical(name), (None, set()))
            if not words & food_words or not words <= common | food_words:
                identity = None
            if canonical(name) in {'bönor', 'svarta bönor'} and not food_words <= words:
                identity = None
        else:
            identity = product_reference(product, name, fact)
        if identity is None:
            return None
        evidence = reference_evidence(identity)
        if form == "cooked_drained" and fact:
            # The supplier's table is retained but cannot establish drained
            # nutrients. Use an explicitly generic drained reference only;
            # never relabel that reference as a product declaration.
            evidence = replace(evidence, field_sources={
                k: (*v, {"kind": "supplier_drained_quantity_reference_basis",
                         "quantity_sources": list(fact.field_sources.get("usable_quantity", ())),
                         "unused_product_nutrition_basis": fact.nutrition_preparation})
                for k, v in evidence.field_sources.items()})
    if evidence.nutrition_unit != unit:
        return None
    if canonical(name) == 'ägg' and fact:
        wrapped = wrap_evidence(recipe, name, evidence)
        return replace(wrapped, field_sources={k: (*v, {'kind': 'edible_purchase_basis',
            'quantity_sources': list(fact.field_sources.get('usable_quantity', ()))})
            for k, v in wrapped.field_sources.items()})
    return wrap_evidence(recipe, name, evidence)


def wrap_evidence(recipe, name, evidence):
    """One provenance-preserving input calculation for bought and pantry food."""
    from app.services.nutrition_reference import NutritionEvidence

    form = recipe.preparation.input_forms[canonical(name)]
    unit = evidence.nutrition_unit
    fields = {
        k: tuple(v)
        + (
            {
                "kind": "recipe_design_input_estimate",
                "version": VERSION,
                "family": recipe.preparation.family,
                "input_form": form,
                "input_evidence_kind": getattr(
                    evidence, "evidence_kind", "qualified_product_declaration"
                ),
                "operation": f"source_per_100_{unit} * used_edible_{unit} / 100 / servings",
                "cooked_quantity_g": None,
                "retention_factor": None,
            },
        )
        for k, v in evidence.field_sources.items()
        if k.startswith("nutrition.")
    }
    if isinstance(evidence, NutritionEvidence):
        return replace(evidence, field_sources=fields, evidence_kind="recipe_design_input_estimate")
    return NutritionEvidence(
        source=evidence.source,
        source_product_id=evidence.source_product_id,
        nutrition=evidence.nutrition,
        nutrition_unit=unit,
        nutrition_basis=evidence.nutrition_basis,
        field_sources=fields,
        evidence_kind="recipe_design_input_estimate",
    )


def pantry_evidence(recipe, name, identity):
    from app.services.nutrition_reference import MAPPINGS, reference_evidence

    validate(recipe)
    form = recipe.preparation.input_forms.get(canonical(name))
    state = MAPPINGS[identity][1]
    compatible = {
        "dry": {"dry"},
        "cooked_drained": {"drained"},
        "raw_edible": {"raw", "raw_skinless_breast", "raw_cod", "raw_farmed"},
        "as_sold": {"ready", "canned_with_liquid", "frozen"},
    }
    if state not in compatible.get(form, set()):
        return None
    return wrap_evidence(recipe, name, reference_evidence(identity))
