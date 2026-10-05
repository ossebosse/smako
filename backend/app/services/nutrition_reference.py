"""Offline generic references. These are NEVER product declarations or GTINs.

SLV cooked component recipes retain their original values. A cooked value is
converted to the measured raw input using the *whole documented final batch*
divided by the raw ingredient amount. WaterFactor is never a total-weight yield.
Only single-food recipes with zero-macro salt are supported by this transform.
"""

import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.services.ingredient_normalizer import canonicalize_ingredient_name

POLICY_VERSION = "slv-component-input-v4"
PATH = Path(__file__).parents[1] / "data/nutrition/slv-20260911.json"
SUPPLEMENT_PATH = PATH.with_name('slv-20260924.json')
APPLE_SUPPLEMENT_PATH = PATH.with_name('slv-20261005-apple.json')
ASSEMBLY_PATH = PATH.with_name("couscous-assembly-20260912.json")
# Explicit reviewed identity + purchased/used preparation. Missing mappings stay missing.
# IDs identify foods, not a retailer product. No prices, organic or allergens here.
MAPPINGS = {
    2481: ("ris", "dry"),
    2475: ("basmatiris", "dry"),
    2477: ("jasminris", "dry"),
    845: ("pasta", "dry"),
    870: ("nudlar", "dry"),
    831: ("couscous", "dry"),
    4457: ("potatis", "raw"),
    289: ("morot", "raw"),
    344: ("gul lök", "raw"),
    4947: ("rödlök", "raw"),
    370: ("vitkål", "raw"),
    325: ("broccoli", "raw"),
    364: ("tomat", "raw"),
    422: ("krossade tomater", "canned_with_liquid"),
    905: ("tofu", "ready"),
    1173: ("kyckling", "raw_skinless_breast"),
    1255: ("lax", "raw_farmed"),
    1246: ("fisk", "raw_cod"),
    951: ("nötfärs 10 %", "raw"),
    2499: ("blandfärs 50 % nöt 50 % gris", "raw"),
    881: ("kikärtor", "dry"),
    884: ("linser", "dry"),
    3815: ("kikärtor", "drained"),
    3816: ("kidneybönor", "drained"),
    3817: ("svarta bönor", "drained"),
    3761: ("stora vita bönor", "drained"),
    1225: ("ägg", "raw"),
    909: ("sojasås", "ready"),
    2189: ("rapsolja", "ready"),
    7266: ("kokosmjölk 18 %", "ready"),
    7139: ("crème fraiche 13 %", "ready"),
    97: ("hårdost 31 %", "ready"),
    123: ("mjölk 3 %", "ready"),
    1975: ("salt", "ready"),
    1162: ("kalkonbröstfilé", "raw"),
    371: ("vitlök", "raw"),
    7193: ("koriander", "raw"),
    7194: ("grönmynta", "raw"),
    339: ("gurka", "raw"),
    4659: ("extra jungfruolivolja", "ready"),
    7137: ("crème fraiche 32 %", "ready"),
    2269: ("ingefära", "raw"),
    980: ("fläskfärs 20 %", "raw"),
    374: ("ärtor", "frozen"),
    574: ("mango", "raw"),
    580: ("persika", "raw"),
    362: ("zucchini", "raw"),
    372: ("aubergine", "raw"),
    4941: ("spenat", "raw"),
    361: ("spenat", "frozen"),
    322: ("blomkål", "raw"),
    323: ("blomkål", "frozen"),
    333: ("champinjoner", "raw"),
    383: ("champinjoner", "frozen"),
    291: ("pepparrot", "raw"),
    377: ("dill", "raw"),
    352: ("persilja", "raw"),
    379: ("basilika", "raw"),
    7199: ("spiskummin", "dry"),
    2306: ("kanel", "dry"),
    7198: ("gurkmeja", "dry"),
    702: ("havregryn", "dry"),
    1941: ("vetemjöl", "dry"),
    321: ("selleri", "raw"),
    294: ("rödbeta", "raw"),
    3765: ("sötpotatis", "raw"),
    350: ("paprika grön", "raw"),
    351: ("paprika röd", "raw"),
    381: ("paprika gul", "raw"),
    392: ("paprika", "raw"),
    402: ("oliver", "drained"),
}
# Optional data availability is explicit for isolated same-facts comparisons.
# Deployed reference files are immutable and included in content_version below.
if APPLE_SUPPLEMENT_PATH.exists():
    MAPPINGS[588] = ("äpple med skal", "raw")
COOKED = {2481: 2515, 870: 2079, 289: 305, 344: 448, 370: 465, 1173: 3594, 1255: 1317, 1246: 1335}
FRIED = {1255: 1316, 1246: 1337}
MACROS = {
    "Energi (kcal)": ("kcal", "kcal"),
    "Protein": ("protein_g", "g"),
    "Kolhydrater, tillgängliga": ("carbs_g", "g"),
    "Fett, totalt": ("fat_g", "g"),
}


def macro_values(rows):
    values = {}
    for row in rows:
        if row.get("namn") not in MACROS:
            continue
        key, unit = MACROS[row["namn"]]
        value = row.get("varde")
        if (
            key in values
            or row.get("enhet", "").lower() != unit
            or row.get("viktGram") != 100
            or row.get("matrisenhetkod") != "W"
            or isinstance(value, bool)
            or not isinstance(value, (float, int))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ValueError("SLV: saknat, konfliktfyllt värde eller fel referensenhet.")
        values[key] = value
    if set(values) != {"protein_g", "carbs_g", "fat_g", "kcal"}:
        raise ValueError("SLV: ofullständiga makron, okänt är inte noll.")
    return values


@lru_cache(maxsize=1)
def reference_data():
    raw = PATH.read_bytes()
    data = json.loads(raw)
    for path in (SUPPLEMENT_PATH, PATH.with_name('slv-20260925.json'), PATH.with_name('slv-20260926.json'), PATH.with_name('slv-20261002.json'), PATH.with_name('slv-20261002-celery.json'), PATH.with_name('slv-20261002-beetroot.json'), PATH.with_name('slv-20261002-sweetpotato.json'), PATH.with_name('slv-20261002-peppers.json'), PATH.with_name('slv-20261003-black-olives.json'), *((APPLE_SUPPLEMENT_PATH,) if APPLE_SUPPLEMENT_PATH.exists() else ())):
        supplement = json.loads(path.read_bytes())
        if data['foods'].keys() & supplement['foods'].keys():
            raise ValueError('SLV supplement must not silently replace retained references')
        data['foods'].update(supplement['foods'])
        data.setdefault('supplements', {})[path.name] = {k: v for k, v in supplement.items() if k != 'foods'}
    for identity in MAPPINGS:
        entry = data["foods"][str(identity)]
        assert entry["food"]["nummer"] == identity
        macro_values(entry["nutrients"])
    mapping = json.dumps([MAPPINGS, COOKED, FRIED, MACROS], sort_keys=True).encode()
    data["assembly_review"] = json.loads(ASSEMBLY_PATH.read_bytes())
    from app.services.reviewed_warm_meals import SOURCES, TEMPLATES, VERSION

    data["warm_review"] = {"version": VERSION, "templates": TEMPLATES, "sources": SOURCES}
    canonical = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    data["content_version"] = POLICY_VERSION + ":" + hashlib.sha256(canonical + mapping).hexdigest()
    return data


def reference_options():
    data = reference_data()
    return [
        {
            "id": f"slv:{n}:{state}",
            "name": data["foods"][str(n)]["food"]["namn"],
            "ingredient": name,
            "preparation": state,
            "unit": "g",
            "preparation_label": {
                "dry": "torr/okokt",
                "raw": "rå",
                "ready": "som såld/ätfärdig",
                "drained": "kokt och avrunnen",
                "canned_with_liquid": "konserv med vätska",
                "raw_skinless_breast": "rå bröstfilé utan skinn",
                "raw_farmed": "rå odlad lax",
                "raw_cod": "rå torsk",
                "frozen": "fryst som såld, före eventuell tillagning",
            }[state],
        }
        for n, (name, state) in MAPPINGS.items()
    ]


def validate_pantry_reference(name, unit, identity):
    option = next((o for o in reference_options() if o["id"] == identity), None)
    if (
        not option
        or unit != "g"
        or canonicalize_ingredient_name(name) != canonicalize_ingredient_name(option["ingredient"])
    ):
        raise ValueError(
            "Skafferiets livsmedel, gram och bekräftade rå/torr/avrunnen form måste stämma med referensen."
        )
    if option["preparation"] in {"raw", "dry"} and any(
        t in name.casefold() for t in ("kokt", "avrun", "tillagad", "konserv")
    ):
        raise ValueError("Rå/torr referens stämmer inte med tillagad eller avrunnen vara.")
    # Meaningful percentages/cut restrictions cannot disappear through canonicalization.
    for percent in re.findall(r"\d+(?:[,.]\d+)?\s*%", option["ingredient"]):
        if percent.replace(" ", "") not in name.replace(" ", ""):
            raise ValueError("Bekräfta även referensens fetthalt/sammansättning i varunamnet.")
    return int(identity.split(":")[1])


@dataclass(frozen=True)
class NutritionEvidence:
    source: str
    source_product_id: str
    nutrition: dict
    nutrition_basis: str
    nutrition_unit: str = "g"
    nutrition_preparation: str = (
        "as_sold"  # Values expressed per input, not stored on ProductFacts.
    )
    field_sources: dict = field(default_factory=dict)
    evidence_kind: str = "generic_reference"
    ingredient: str = ""


def reference_evidence(identity, *, cooked=False, declaration=None, method="boil"):
    data = reference_data()
    entry = data["foods"][str(identity)]
    raw_values = macro_values(entry["nutrients"])
    values = raw_values
    history = []
    if cooked:
        if method not in {"boil", "fry"} or (method == "fry" and identity not in FRIED):
            return None
        if identity not in COOKED:
            return None
        prepared_id = FRIED[identity] if method == "fry" else COOKED[identity]
        prepared = data["preparations"][str(prepared_id)]
        ingredients = prepared["ingredients"]
        main = [i for i in ingredients if i["nummer"] == identity]
        if len(main) != 1 or any(i["nummer"] not in {identity, 1975} for i in ingredients):
            return None  # Never accidentally include added fat or another food.
        if any(macro_values(data["foods"]["1975"]["nutrients"]).values()):
            return None
        before = main[0]["viktForeTillagning"]
        weights = [i.get("viktEfterTillagning") for i in ingredients]
        if (
            not before
            or before <= 0
            or any(
                not isinstance(v, (float, int)) or not math.isfinite(v) or v <= 0 for v in weights
            )
        ):
            return None
        total_after = sum(weights)
        values = {
            k: v * total_after / before for k, v in macro_values(prepared["nutrients"]).items()
        }
        if any(v < 0 for v in values.values()):
            return None
        history = [
            {
                "cooked_food_id": prepared_id,
                "raw_food_id": identity,
                "raw_input_g": before,
                "documented_final_batch_g": total_after,
                "operation": "cooked_per100g * final_batch_g / raw_input_g",
                "source_url": prepared["source_url"],
                "data_version": prepared["food"]["version"],
                "retrieved_at": prepared.get("retrieved_at", data["retrieved_at"]),
                "other_reference_ingredients_subtracted": [
                    i for i in ingredients if i["nummer"] not in {identity, 1975}
                ],
                "water_factor_applied_to_total_weight": False,
            }
        ]
        if declaration:
            # Apply documented food-specific changes to a compatible declaration.
            values = {k: v for k, v in values.items() if k in declaration.nutrition}
            if any(
                raw_values[k] == 0 and (values[k] != 0 or declaration.nutrition[k] != 0)
                for k in values
            ):
                return None
            values = {
                k: declaration.nutrition[k] * values[k] / raw_values[k]
                if raw_values[k]
                else declaration.nutrition[k]
                for k in values
            }
            history.append(
                {
                    "operation": "qualified_declaration * cooked_input_reference / raw_reference",
                    "declaration_source": declaration.source,
                }
            )
    description = entry["food"]["namn"]
    version = entry["food"]["version"]
    kind = "documented_preparation_estimate" if cooked else "generic_reference"
    return NutritionEvidence(
        source=f"Livsmedelsverkets Livsmedelsdatabas {version[:10]}",
        source_product_id=f"slv:{identity}",
        nutrition=values,
        nutrition_basis=f"{description}; per 100 g uppmätt ätbar ingrediens i {next(o['preparation_label'] for o in reference_options() if o['id'].startswith(f'slv:{identity}:'))} form. "
        + (
            "Bas: kvalificerad produktdeklaration med dokumenterad tillagningsjustering. "
            if declaration
            else "Bas: generiskt referensvärde, inte produktdeklaration. "
        )
        + (
            "Tillagning enligt dokumenterat livsmedelsspecifikt beräkningsunderlag; faktisk förlust kan avvika."
            if cooked
            else "Generiskt referensvärde, inte produktens deklaration."
        ),
        field_sources={
            f"nutrition.{k}": (
                {
                    "food_id": identity,
                    "description": description,
                    "data_version": version,
                    "retrieved_at": entry.get("retrieved_at", data["retrieved_at"]),
                    "source_url": entry["source_url"],
                    "license": data["license"],
                    "transformations": history,
                    "kind": kind,
                },
            )
            for k in values
        },
        evidence_kind=kind,
        ingredient=MAPPINGS[identity][0],
    )


def product_reference(product, name, facts):
    """Narrow reviewed plain-food mappings; never fix conflicting facts with estimates."""
    if facts and facts.conflicts:
        return None
    from app.services.recipe_ingredient_references import reviewed_reference

    reference = reviewed_reference(product, name, facts)
    if reference is not None:
        return reference
    text = product.name.casefold()
    canonical = canonicalize_ingredient_name(name)
    if canonical in {'kycklingbröstfilé', 'kycklingfilé'}:
        canonical = 'kyckling'
    composition = " ".join(facts.ingredients).casefold() if facts else ""
    if canonical in {"potatis", "vitlök"}:
        # Ingredient form is independent of having a complete declaration.
        # Ready dishes, spice jars and oil mixtures do not establish raw input.
        category = (product.category or "").casefold()
        if re.search(r"krydd|pulver|tork|granulat|salt|peppar|kroket|puré|pure|sallad|gratäng|stekt|kokt|rostad|olja|smör|pinsa|bearnaise|vitost", text + " " + category):
            return None
        words = set(re.findall(r"[a-zåäö]+", composition))
        food_words = {canonical, "ingredienser", "ekologisk", "ekologiska"}
        if composition and not words <= food_words:
            return None
        source_text = " ".join(o.description or "" for o in product.offers)
        fresh = (any(t in category for t in ("frukt", "grönsak", "potatis", "lök"))
                 or bool(re.search(r"\bKlass\s+1\b", source_text, re.IGNORECASE)))
        if canonical == "potatis":
            if fresh and re.fullmatch(r"(?:ekologisk |svensk )?(?:färskpotatis|delikatesspotatis|mandelpotatis|minipotatis|potatis)(?: (?:fast|mjölig|tvättad|eko|ekologisk|ekologiska|klass 1|sverige|svensk|i påse|[\d,.]+\s*(?:g|kg)))*", text):
                return 4457
            return None
        if fresh and re.fullmatch(r"(?:ekologisk |färsk )?vitlök(?: (?:hackad|krossad|finhackad|skalad|eko|ekologisk|i kapsel|[\d,.]+\s*g))*", text):
            return 371
        return None
    if canonical == 'ägg' and re.match(r'^(?:ägg|skåneägg|bruna ägg)\b', text):
        words = set(re.findall(r'[a-zåäö]+', composition))
        return 1225 if words and words <= {'ingredienser', 'krav', 'ekologiska', 'ägg'} else None
    if canonical == "rödlök":
        # A distinct plain fresh food, never yellow onion or a pickled/flavoured
        # product. The existing SLV record was retained but never mapped here.
        return 4947 if re.fullmatch(r"(?:rödlök|röd lök)(?: eko| ekologisk| ekologiska)?", text.strip()) and not composition else None
    # Edition/retailer-independent identities of plain foods. These are generic
    # measured edible-input references, never product declarations or density
    # estimates. Unknown mint species, oil blends, seasoning and cooked forms
    # deliberately have no mapping.
    plain = re.sub(r'\s+', ' ', text).strip()
    plain = re.sub(r'\s+\d+(?:[,.]\d+)?\s*g$', '', plain)
    if not composition:
        # A plain fresh fruit identity only; no piece-to-edible-gram conversion.
        if plain == 'mango' and canonical == 'mango' and 'Frukt & grönsaker' in (product.category or '').split(' > '):
            return 574
        rules = (
            (371, {'vitlök'}, r'(?:ekologisk )?vitlök(?: i kapsel)?'),
            (7193, {'koriander'}, r'(?:färsk )?koriander(?: blad)?'),
            (7194, {'grönmynta'}, r'(?:färsk )?grönmynta(?: blad)?'),
            (339, {'gurka'}, r'(?:ekologisk )?gurka(?: ej ekologisk)?'),
            (1162, {'kalkonbröstfilé', 'kalkonfilé'}, r'(?:färsk )?kalkonbröstfilé'),
            (4659, {'olivolja', 'extra jungfruolivolja', canonicalize_ingredient_name(plain)},
             r'(?:ekologisk |spansk )?(?:extra jungfruolivolja|olivolja italiensk extra virgin)'),
            (7137, {'crème fraiche'}, r'crème fraiche 32\s*%'),
            (2269, {'ingefära'}, r'(?:ekologisk |färsk )?ingefära'),
            (980, {'fläskfärs', 'fläskfärs 20%'}, r'fläskfärs 20\s*%'),
            (374, {'ärtor'}, r'(?:nordiska |gröna )?ärtor djupfrysta'),
        )
        for identity, names, pattern in rules:
            if (canonical in names or name.strip().casefold() == product.name.strip().casefold()) and re.fullmatch(pattern, plain):
                if identity in {371, 7193, 7194, 339, 2269}:
                    source_text = ' '.join(o.description or '' for o in product.offers)
                    if not ('färsk' in plain or re.search(r'\bKlass\s+1\b', source_text, re.IGNORECASE)):
                        return None  # A bare herb name does not prove fresh leaf versus dried spice.
                return identity
    if canonical == "linser":
        return (
            884
            if (
                "röd" in text
                and "lins" in text
                and composition
                and not any(t in composition for t in ("vatten", "kokta", "salt", "lake"))
            )
            else None
        )
    if canonical == "pasta":
        return (
            845
            if (
                re.fullmatch(r"(?:spaghetti|pasta|penne|fusilli|makaroner)", text.strip())
                and "durumvete" in composition
                and not any(t in composition for t in ("fullkorn", "linser", "ärtor", "bönor"))
            )
            else None
        )
    if canonical == "krossade tomater":
        return (
            422
            if (
                "kross" in text
                and "tomat" in text
                and composition
                and not any(t in text for t in ("chili", "vitlök", "basilika"))
            )
            else None
        )
    if any(
        t in text
        for t in (
            "mariner",
            "paner",
            "rökt",
            "krydd",
            "färdig",
            "sallad",
            "sås",
            "paté",
            "special",
            "olja",
            "konserv",
            "pinklax",
            "frysta moröt",
            "babymoröt",
        )
    ):
        return None
    if (
        facts
        and facts.ingredients
        and any(
            t in " ".join(facts.ingredients).casefold()
            for t in ("saltlake", "marinad", "stabiliseringsmedel", "vatten")
        )
    ) and canonical != "tofu":
        return None
    if canonical == "couscous":
        return 831 if re.fullmatch(r"couscous(?: eko| ekologisk)?", text.strip()) else None
    if canonical == "tofu":
        return (
            905
            if (
                "tofu" in text
                and "naturell" in text
                and "fast" in text
                and not any(t in text for t in ("silke", "mjuk", "lag", "rök", "ferment"))
            )
            else None
        )
    if canonical == "tomat":
        plain = re.fullmatch(
            r"(?:tomat|tomater|körsbärstomater|kvisttomater|plommontomat|plommontomater|tomater plommon|cocktailtomater|pärltomater)(?: eko| ekologiska)?",
            text.strip(),
        )
        fresh = plain or (
            "tomat" in text and any(t in text for t in ("klass 1", "i ask", "lösvikt"))
        )
        ingredients = " ".join(facts.ingredients).casefold() if facts else ""
        return (
            364
            if (
                fresh
                and not any(
                    t in text + " " + ingredients
                    for t in (
                        "skalad",
                        "kross",
                        "puré",
                        "pure",
                        "passer",
                        "tork",
                        "grill",
                        "juice",
                        "soppa",
                        "lag",
                        "ketchup",
                        "frys",
                        "pasta",
                        "inlag",
                        "pelat",
                        "hela",
                        "citronsyra",
                    )
                )
            )
            else None
        )
    if canonical == "ris":
        if any(
            t in text + " " + composition
            for t in (
                "basmati",
                "jasmin",
                "fullkorn",
                "råris",
                "svart",
                "röd",
                "parboiled",
                "snabb",
                "grötris",
            )
        ):
            return None
        return 2481 if "långkorn" in text else None
    if canonical == "nudlar":
        return (
            870
            if "äggnud" in text
            and not any(t in text for t in ("fullkorn", "risnud", "glasnud", "snabb"))
            else None
        )
    if canonical == "kyckling":
        return (
            1173
            if "kyckling" in text and ("bröstfil" in text or "kycklingfil" in text)
            and not any(t in text for t in ("lår", "skinn", "innerfil"))
            else None
        )
    if canonical == "nötfärs":
        fat = facts.nutrition.get("fat_g") if facts else None
        return 951 if "nötfärs" in text and (fat == 10 or re.search(r"\b10\s*%", text)) else None
    if canonical == "fisk":
        return (
            1246
            if "torsk" in text
            and "filé" in text
            and not any(t in text for t in ("rimmad", "lever"))
            else None
        )
    if canonical == "lax":
        return (
            1255
            if ("laxfilé" in text or "laxfile" in text)
            and not any(t in text for t in ("vild", "grav", "skinn"))
            else None
        )
    return {"morot": 289, "gul lök": 344, "vitkål": 370, "tomat": 364, "broccoli": 325}.get(
        canonical
    )


def assembly_evidence(identity, declaration=None):
    """Only the reviewed no-discard couscous/tofu/tomato assembly, after opt-in."""
    if identity not in {831, 905, 364}:
        return None
    reference = reference_evidence(identity)
    review = reference_data()["assembly_review"]
    values = declaration.nutrition if declaration else reference.nutrition
    source = declaration.source if declaration else reference.source
    field_sources = declaration.field_sources if declaration else reference.field_sources
    return NutritionEvidence(
        source=source,
        source_product_id=declaration.source_product_id
        if declaration
        else reference.source_product_id,
        nutrition=values,
        nutrition_basis=(
            "Per 100 g använd ätbar ingrediens som såld; "
            + ("produktdeklaration. " if declaration else "generisk SLV-referens. ")
            + "Couscous sväller i vatten utan avrinning; tofu och tomat serveras utan värmning. "
            "Uppskattning från använd mängd, inte uppmätt näringsretention eller tillagad vikt."
        ),
        evidence_kind="reviewed_assembly_estimate",
        ingredient=MAPPINGS[identity][0],
        field_sources={
            f"nutrition.{k}": tuple(field_sources.get(f"nutrition.{k}", ()))
            + (
                {
                    "kind": "reviewed_assembly_estimate",
                    "food_id": identity,
                    "review": review,
                    "operation": "as_sold_macros * used_edible_input_g / 100",
                    "cooked_quantity_g": None,
                    "discarded_food_g": 0,
                    "package_surplus_included": False,
                },
            )
            for k in values
        },
    )
