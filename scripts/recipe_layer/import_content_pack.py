"""Deterministic adapter for the supplied, immutable 24+24 authored package.

Run from the repository with PYTHONPATH=backend. No network, model, product,
price or nutrient synthesis. Priority 1 precedes 2 in the emitted registry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from app.models.recipe import Recipe, RecipePreparation
from app.services.recipe_library import _structural_check, content_hash

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "backend/app/data/recipes"
SOURCE = DATA / "content-pack-20261004/recipe_content.json"
SOURCE_SHA256 = "492af59612d7b8ae9ad4b8eb9f2292fc3515f61a1d2aac9edc15464b08a3b36d"
OUTPUT = DATA / "content-pack-20261004/registered.json"
CUISINES = {"GR": "greek", "IT": "italian", "MX": "mexican", "IN": "indian", "TH": "thai", "SE": "swedish"}

# Culinary review against all 104 current issued versions, not title matching.
# Family identity is deliberately conservative: a different starch/protein alone
# does not manufacture a new family. Each decision is exported for review.
# proposal: (existing family or new slug, method, side, nearest family, rationale)
FAMILIES = {
    "GR01": ("smako-greek-souvlaki", "pan", "bröd", "smako-greek-souvlaki", "Samma oregano-, kål- och yoghurtfyllda brödmåltid; pita och kyckling motiverar egna variationer, inte en ny grundrätt."),
    "GR02": ("bean-small-pasta", "pot", "pasta", "smako-greek-spanakorizo", "Småpasta sjuder i tomat med vita bönor; annan metod, sås och struktur än spenatris med kikärtor."),
    "GR03": ("smako-greek-fish-plaki", "oven", "potatis", "smako-greek-fish-plaki", "Ugnsfisk med citron och tomat; potatis, ärtor och dillkräm är en motiverad hel variation av fiskfamiljen."),
    "GR04": ("roasted-carrot-legumes", "oven", "couscous", "smako-greek-gigantes", "Torrostad morot och baljväxter med kall kräm, inte bönor bakade i tomatsås; separat plåträtt."),
    "IT01": ("mushroom-gnocchi-pan", "pan", "gnocchi", "smako-italian-mushroom-risotto", "Kokning följd av stekning av gnocchi/potatis med bönor; ingen risotto eller linsris."),
    "IT02": ("tomato-braised-chicken", "pot", "pasta", "smako-italian-polpette", "Bitar bräseras med kål, morot och oliver; annan huvudkomponent och bräsering än formade färsbullar."),
    "IT03": ("lemon-pasta-salad", "salad", "pasta", "smako-italian-piccata", "Ljummen sallad med avrunna proteiner, råa grönsaker och citrondressing; ingen varm piccatasås."),
    "IT04": ("tortilla-pizza", "oven", "bröd", "smako-italian-spinach-pasta-bake", "Tunt krispigt tortillabröd med svamp och keso/bönkräm; pizza, inte pastagratäng."),
    "MX01": ("bean-tostadas", "oven", "bröd", "smako-mexican-bean-enchiladas", "Öppna torra krispiga bröd med mosad bönröra och rå kål; inte rullar bakade i tomatsås."),
    "MX02": ("smoky-potato-pan", "pan", "potatis", "smako-mexican-chicken-bowl", "Förkokt potatis steks med huvudråvaran och rökt paprika; ingen risbowl eller separat salsa."),
    "MX03": ("mushroom-quesadillas", "pan", "bröd", "smako-mexican-corn-soup", "Fylld quesadilla är huvudrätt med svamp och bönor/kyckling; den befintliga måltidens huvudkomponent är soppa."),
    "MX04": ("smako-mexican-lentil-chili", "pot", "kål", "smako-mexican-lentil-chili", "Tomat- och kryddsjudad lins/färspanna med majs, ost och kål; variation av chilifamiljen utan ris."),
    "IN01": ("smako-indian-chana-cauliflower", "pot", "potatis", "smako-indian-chana-cauliflower", "Samma baljväxtmasala och gurkyoghurt; rostad potatis ersätter ris och blomkål inom en fullskriven variation."),
    "IN02": ("smako-indian-tofu-dal", "pot", "ris", "smako-indian-tofu-dal", "Tomat-linsgryta med ris och syrlig kål; kyckling/tofu är motiverade variationer av dalfamiljen."),
    "IN03": ("masala-pasta", "pan", "pasta", "smako-indian-palak-tofu", "Tomat-yoghurtsås och kort pasta i stället för spenatgryta och vitlöksris; egen sammanhållen pastarätt."),
    "IN04": ("roasted-cauliflower-dal", "oven", "linser", "smako-indian-tofu-dal", "Rostad blomkål/tofu eller kikärtor är huvudkomponent på separat kokoslinssås; saknar ris och grytans struktur."),
    "TH01": ("sour-noodle-salad", "salad", "nudlar", "smako-thai-peanut-noodles", "Syrlig sallad med rå kål, lime-sojadressing och hela jordnötter; inte varm krämig jordnötssås."),
    "TH02": ("smako-thai-chicken-coconut-curry", "pot", "ris", "smako-thai-chicken-coconut-curry", "Kokosbräsering med ris, paprika och lime; spenat och fisk/kyckling gör detta till variationer av curryfamiljen."),
    "TH03": ("smako-thai-basil-tofu", "pan", "ris", "smako-thai-basil-tofu", "Basilikastekt färs/tofu med soja, grönsaker och ris; samma grundrätt med fullskriven kål- och vitlöksrisvariation."),
    "TH04": ("smako-thai-tofu-satay", "oven", "nudlar", "smako-thai-tofu-satay", "Rostad tofu/broccoli och gurka; nudlar med soja-ingefärsglaze är en motiverad sås- och tillbehörsvariation."),
    "SE01": ("spinach-oven-pancake", "oven", "pannkaka", "smako-italian-spinach-pasta-bake", "Ägg-mjölksmet med keso bakas som ugnspannkaka; annan struktur och metod än pastagratäng."),
    "SE02": ("fish-potato-gratin", "oven", "potatis", "smako-swedish-mustard-salmon", "Fisk och grönsaker bakas under mosat potatistäcke; gratäng, inte separat fiskfilé och kokt potatis."),
    "SE03": ("smako-swedish-tofu-root-hash", "pan", "potatis", "smako-swedish-tofu-root-hash", "Potatis- och rotfruktspanna med protein och senapskräm; stekt svamp/bön- eller kycklingvariation av pyttfamiljen."),
    "SE04": ("smako-swedish-mustard-chicken", "oven", "potatis", "smako-swedish-mustard-chicken", "Kyckling/tofu och potatis med senapskräm; ugn, äpple och rotfrukter ger en full metodvariation."),
}

NAMES = dict(zip(
    ["chicken_thigh", "chicken_breast", "cod", "salmon", "pork_mince", "tofu", "white_beans", "black_beans", "chickpeas", "tuna", "red_lentils", "rice", "pasta", "small_pasta", "couscous", "rice_noodles", "egg_noodles", "pita", "tortilla", "gnocchi", "flour", "potato", "carrot", "cabbage", "onion", "red_onion", "garlic", "ginger", "cucumber", "tomato", "pepper", "mushroom", "spinach", "peas", "corn", "broccoli", "cauliflower", "apple", "crushed_tomato", "tomato_paste", "olives", "yogurt", "creme_fraiche", "feta", "cottage_cheese", "hard_cheese", "milk", "egg", "coconut_milk", "lemon_juice", "lime_juice", "oil", "soy_sauce", "mustard", "peanut_butter", "peanuts", "sugar", "oregano", "basil", "dill", "parsley", "cumin", "paprika_powder", "smoked_paprika", "turmeric", "coriander_seed", "chili", "salt", "black_pepper", "water"],
    ["kyckling", "kyckling", "fisk", "lax", "fläskfärs", "tofu", "bönor", "svarta bönor", "kikärtor", "tonfisk", "linser", "ris", "pasta", "pasta", "couscous", "nudlar", "nudlar", "bröd", "tortillas", "gnocchi", "vetemjöl", "potatis", "morot", "vitkål", "gul lök", "rödlök", "vitlök", "ingefära", "gurka", "tomat", "paprika", "champinjoner", "spenat", "ärtor", "majs", "broccoli", "blomkål", "äpple", "krossade tomater", "tomatpuré", "oliver", "yoghurt naturell", "crème fraiche", "fetaost", "keso", "ost", "mjölk", "ägg", "kokosmjölk", "citronjuice", "limejuice", "rapsolja", "sojasås", "senap", "jordnötssmör", "jordnötter", "strösocker", "oregano", "basilika", "dill", "persilja", "spiskummin", "paprikapulver", "rökt paprikapulver", "gurkmeja", "malen koriander", "chiliflakes", "salt", "svartpeppar", "vatten"], strict=True))
FORMS = {"raw_edible": "raw_edible", "dry_as_purchased": "dry", "as_sold_edible": "as_sold",
             "volume_as_sold": "as_sold", "frozen_as_purchased": "as_sold", "cooked_drained": "cooked_drained",
             "process_water": "process_water"}
REQUIREMENTS = {
    "white_beans": ["white_beans"], "tofu": ["plain", "firm"], "yogurt": ["plain", "thick"],
    "red_lentils": ["red_split"], "rice": ["white_rice"], "lemon_juice": ["pure_juice"],
    "lime_juice": ["pure_juice"], "oregano": ["dried_leaf"], "cumin": ["ground"],
    "paprika_powder": ["ground"], "turmeric": ["ground"], "peanut_butter": ["plain"],
}
SAFETY_STEPS = {
    "GR01": 4, "GR03": 3, "IT02": 3, "MX02": 4, "MX03": 3, "MX04": 2,
    "IN02": 3, "IN03": 3, "TH01": 3, "TH02": 4, "TH03": 4, "TH04": 2,
    "SE01": 3, "SE02": 4, "SE03": 4, "SE04": 2,
}
SAFETY_TEXT = {
    "poultry": "Kontrollera med termometer att kycklingens tjockaste del når minst 74 °C; tiden är vägledande.",
    "ground_meat": "Kontrollera med termometer att fläskfärsen når minst 71 °C.",
    "fish": "Kontrollera med termometer att fiskens tjockaste del når minst 63 °C.",
    "egg_dish": "Kontrollera med termometer att äggrätten når minst 71 °C; om den också är gratäng gäller 74 °C.",
    "casserole": "Kontrollera med termometer att gratängens mitt når minst 74 °C.",
}
METHOD_NOTE = ("Näringen uppskattas från de använda ätbara ingredienserna före tillagning, delat på portionerna. "
               "Mätt retention och tillagad vikt saknas. Förluster till kokvatten, panna och redskap är inte uppmätta. "
               "Följ receptets anvisning om avhällning; lägg inte till olja eller mat utöver angivna mängder. "
               "Dricksvatten till tillagning är en processuppgift, inte en inköpsvara.")


def build(priority=2):
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA256
    source = json.loads(raw)
    catalog = source["ingredient_catalog"]
    assert set(catalog) == set(NAMES)
    result = []
    for r in sorted(source["recipe_versions"], key=lambda r: (r["priority"], r["family_proposal_id"], r["variant_kind"] != "base_proposal")):
        if r["priority"] > priority:
            continue
        family = r["family_proposal_id"]
        target, method, side, _, _ = FAMILIES[family]
        cuisine = CUISINES[family[:2]]
        overlap = target.startswith("smako-")
        base_id = target if overlap else f"smako-{cuisine}-{target}"
        totals = defaultdict(float)
        first_component = {}
        components = []
        for c in r["components"]:
            amounts = []
            for i in c["ingredients"]:
                key = i["key"]
                totals[key] += i["quantity"]
                first_component.setdefault(key, c["component_id"])
                form = "preserved_drained" if key == "olives" else "as_sold" if key == "salt" else FORMS[i["quantity_basis"]]
                amounts.append({"ingredient_key": f"{NAMES[key]}|{form}", "quantity": i["quantity"], "unit": i["unit"], "note": i["prep_note_sv"], "name": catalog[key]["name_sv"]})
            components.append({"id": c["component_id"], "name": c["name_sv"], "amounts": amounts})
        ingredients = []
        for key, quantity in totals.items():
            if key == "water":
                continue  # retained exactly in component allocations, not bought
            cat = catalog[key]
            form = "preserved_drained" if key == "olives" else "as_sold" if key == "salt" else FORMS[cat["quantity_basis"]]
            requirements = [*REQUIREMENTS.get(key, []), f"pack:{key}"]
            if cat["quantity_basis"] == "frozen_as_purchased":
                requirements.extend(["plain", "frozen"])
            ingredients.append({"name": NAMES[key], "canonical_name": NAMES[key], "quantity": round(quantity, 8),
                "unit": cat["recipe_unit"], "form": form, "component": first_component[key], "required": True,
                "role": "primary" if key in r["primary_protein_keys"] else "flavour",
                "quantity_min": round(quantity, 8), "quantity_max": round(quantity, 8), "quantity_step": 0.01,
                "product_requirements": requirements})
        steps = []
        for s in r["steps"]:
            text = s["instruction_sv"]
            number = int(s["step_id"][1:])
            if number == SAFETY_STEPS.get(family):
                text += " " + " ".join(SAFETY_TEXT[k] for k in r["safety_profile_ids"] if k in SAFETY_TEXT)
            keys = sorted({a["ingredient_key"] for c in components if c["id"] in s["component_ids"]
                           for a in c["amounts"] if a["ingredient_key"] != "vatten|process_water"})
            tokens = ({"5 ml": 5} if r["proposal_id"] == "IT03-tofu" and number == 2 else
                      {"10 ml": 10} if r["proposal_id"] == "IT03-tofu" and number == 3 else
                      {"50 ml": 50} if family == "SE02" and number == 3 else None)
            steps.append({"id": s["step_id"], "text": text.strip(), "ingredient_keys": keys, "depends_on": s["depends_on"],
                              "duration_minutes": s["duration_minutes_estimate"], "scalable_amounts": tokens})
        primary = NAMES[r["primary_protein_keys"][0]]
        slug = r["proposal_id"].lower()
        design = {"base_id": base_id, "version": "2.0.0", "variant_id": slug if overlap or r["variant_kind"] != "base_proposal" else "base",
            "cuisines": [cuisine], "family": base_id.removeprefix("smako-"), "primary_ingredient": primary, "method": method,
            "side": "potatis" if r["proposal_id"] == "IT01-potatis" else side,
            "flavor_profile": r["culinary_character_sv"], "components": components, "steps": steps,
            "estimated_minutes": r["time"]["total_minutes_estimate"], "equipment": r["equipment_sv"],
            "vegetarian": r["diet_intent"] == "vegetarian_candidate_requires_product_check", "fish": bool(set(totals) & {"cod", "salmon", "tuna"}),
            "ingredient_count": r["ingredient_count_excluding_salt_pepper_water"],
            "provenance": {"reviewed_at": "2026-10-05", "notes": "Levererat originalinnehåll. Anpassning granskad mot komponentmängder och fulla egna variantsteg. Inte provlagat; köp, allergener och näring kvalificeras separat."},
            "content_sha256": "0" * 64, "content_source": {"pack_id": source["pack_id"], "proposal_id": r["proposal_id"],
                "sha256": SOURCE_SHA256, "priority": r["priority"], "timing_basis": "authored_estimate_coarse_dependencies",
                "active_minutes": r["time"]["active_minutes_estimate"], "method_note": METHOD_NOTE,
                "scaling_note": r["scaling_rule_sv"], "safety_sources": [source["sources"][s]["url"] for k in r["safety_profile_ids"] for s in source["shared_safety_profiles"][k]["source_ids"]]}}
        if isinstance(design["flavor_profile"], str):
            design["flavor_profile"] = [design["flavor_profile"]]
        recipe = Recipe.model_validate({"name": r["name_sv"], "servings": 2, "ingredients": ingredients,
                                            "instructions": [s["text"] for s in steps], "design": design})
        digest = content_hash(recipe)
        recipe = recipe.model_copy(update={"design": recipe.design.model_copy(update={"content_sha256": digest}),
            "preparation": RecipePreparation(version="smako-authored-input-v2", origin="smako_recipe_design",
                parent_sha256=digest, family=design["family"], input_forms={i.canonical_name: i.form for i in recipe.ingredients})})
        _structural_check(recipe)
        result.append(recipe.model_dump(mode="json"))
    return {"library_version": "smako-content-pack-20261004-v1", "source_sha256": SOURCE_SHA256, "recipes": result}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--priority", type=int, choices=(1, 2), default=2)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = (json.dumps(build(args.priority), ensure_ascii=False, indent=2) + "\n").encode()
    if args.check:
        assert OUTPUT.read_bytes() == encoded, "Registered content differs from deterministic import"
    else:
        OUTPUT.write_bytes(encoded)
    print(hashlib.sha256(encoded).hexdigest())
