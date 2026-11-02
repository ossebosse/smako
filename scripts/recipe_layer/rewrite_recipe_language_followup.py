"""Second, independently receipted language review; never rewrite issued packs."""
from __future__ import annotations

import argparse
import copy
import re

import rewrite_recipe_language as first

REPORT = first.ROOT.parents[3] / "docs/reviews/recipe-language-followup-20261102"
WORK = first.ROOT.parents[3] / ".local/recipe-language-followup-20261102"
NOUNS = {
    "bönor": "bönorna", "fisk": "fisken", "fläskfärs": "fläskfärsen",
    "fläskkött": "fläskköttet", "gröna linser": "de gröna linserna",
    "gröna mungbönor": "mungbönorna", "halloumi": "halloumin", "keso": "keson",
    "kidneybönor": "kidneybönorna", "kikärtor": "kikärtorna", "kyckling": "kycklingen",
    "lammkött": "lammköttet", "lax": "laxen", "linser": "linserna", "nötfärs": "nötfärsen",
    "nötkött": "nötköttet", "ost": "osten", "paneer": "paneeren",
    "svarta bönor": "de svarta bönorna", "svarta linser": "de svarta linserna",
    "tempeh": "tempehn", "tofu": "tofun", "ägg": "äggen",
}
PLURAL = {"bönor", "gröna linser", "gröna mungbönor", "kidneybönor", "kikärtor",
          "linser", "svarta bönor", "svarta linser", "ägg"}
NEUTER = {"fläskkött", "lammkött", "nötkött"}
VEGETABLES = {
    "aubergine": "auberginen", "broccoli": "broccolin", "gul lök": "löken",
    "morot": "moroten", "paprika": "paprikan", "pumpa": "pumpan",
    "rödbeta": "rödbetan", "tomat": "tomaten", "zucchini": "zucchinin",
    "champinjoner": "champinjonerna", "bambuskott": "bambuskotten",
}
VAGUE_CHECK = "Kontrollera att huvudkomponenten är genomvarm och att grönsakerna har den beskrivna konsistensen."
TAMARIND_LABEL = "Tamarindkoncentrat CHS, uppmätt volym; ny receptdos"


def joined(values):
    return " och ".join([", ".join(values[:-1]), values[-1]]) if len(values) > 1 else values[0]


def rewrite_step(text, recipe, step):
    original = text
    text = text.replace("Arbeta med sked så att huvudråvaran binder de finhackade grönsakerna.",
                        "Rör med sked tills grönsakerna är jämnt fördelade och smeten håller ihop.")
    text = text.replace("Arbeta ihop tills riset håller samman med huvudråvaran.",
                        "Arbeta ihop tills riset är jämnt fördelat i smeten och den håller samman.")
    if text.startswith("Vänd försiktigt ner ") and "i den tillagade huvudråvaran" in text:
        text = text.replace("Vänd försiktigt ner ", "Blanda försiktigt ", 1).replace("i den tillagade huvudråvaran", "med den tillagade huvudråvaran")
    primary = recipe["design"]["primary_ingredient"]
    noun = NOUNS.get(primary)
    plural = primary in PLURAL
    if "huvudråvar" in text:
        if noun is None:
            raise ValueError((recipe["name"], "Unreviewed primary ingredient", primary))
        # Attributive Swedish agreement: the plural article must also follow the food.
        prepared = ("de " if plural else "det " if primary in NEUTER else "den ") + "tillagade " + noun.removeprefix("de ")
        text = text.replace("den tillagade huvudråvaran", prepared)
        text = text.replace("den färdiga huvudråvaran", prepared.replace("tillagade", "färdiga"))
        text = text.replace("den mjuka, pocherade huvudråvaran", "den pocherade kycklingen")
        text = text.replace("huvudråvarans", noun + "s")
        text = text.replace("huvudråvaran", noun).replace("huvudråvara", noun)
        text = text.replace(f"{noun} är färdig", f"{noun} är " + ("färdiga" if plural else "färdigt" if primary in NEUTER else "färdig"))
    if VAGUE_CHECK in text:
        # These families already specify the outer crust, set centre or soft shell.
        if text.startswith(("Baka mitt i ugnen", "Ånga cirka", "Lägg de fyllda")):
            check = "Kontrollera även att blandningen är genomvarm i mitten." if text.startswith("Ånga cirka") else ""
        elif text.startswith("Värm oljan till huvudrätten i en bred stekpanna. Stek i omgångar"):
            check = "Kontrollera att biffarna är genomvarma i mitten."
        else:
            if noun is None:
                raise ValueError((recipe["name"], "Unreviewed doneness check"))
            check = f"Kontrollera att {noun} är " + ("genomvarma" if plural else "genomvarmt" if primary in NEUTER else "genomvarm")
            vegetables = [VEGETABLES[k.split("|")[0]] for k in step["ingredient_keys"] if k.split("|")[0] in VEGETABLES]
            if vegetables:
                check += " och att " + joined(vegetables) + (" är mjuk" if len(vegetables) == 1 and vegetables[0] not in {"champinjonerna", "bambuskotten"} else " är mjuka")
            check += "."
        text = text.replace(VAGUE_CHECK, check)
        if noun:
            text = text.replace(f"Stek {primary} på medelvärme under omrörning tills genomvarm och färdig. {check}",
                                f"Stek {noun} på medelvärme under omrörning tills " + ("de är genomvarma." if plural else "den är genomvarm."))
        if text.startswith("Sjud på låg värme"):
            # The concrete check already says what is ready; keep the time once.
            text = re.sub(r"(Sjud på låg värme cirka \d+ minuter) tills .*?\. Rör då och då\. ", r"\1. Rör då och då. ", text)
    replacements = {
        "Servera de färdiga huvudkomponenterna och samtliga ätliga tillbehör tillsammans. Fördela maten över det angivna antalet portioner. Processmaterial som enligt tidigare steg ska avlägsnas eller kasseras ingår inte i serveringen.":
            "Servera rätten med alla tillbehör och fördela maten jämnt mellan portionerna. Servera inte sådant som ska tas bort enligt tidigare steg.",
        "båda huvudkomponenterna": "både riset och kycklingen",
        "huvudkomponentens alla ingredienser": "ingredienserna till huvudrätten",
        "alla huvudkomponentens ingredienser": "alla ingredienser till huvudrätten",
        "huvudkomponentens hela oljemängd": "all olja till huvudrätten",
        "huvudkomponentens råa ägg": "de råa äggen till huvudrätten",
        "huvudkomponentens ägg": "äggen till huvudrätten",
        "huvudkomponentens bönor": "bönorna till huvudrätten",
        "huvudkomponentens olivolja": "olivoljan till huvudrätten",
        "huvudkomponentens frysta spenat": "den frysta spenaten till huvudrätten",
        "huvudkomponentens förberedda rödbeta": "den förberedda rödbetan till huvudrätten",
        "huvudkomponentens förberedda potatis": "den förberedda potatisen till huvudrätten",
        "huvudkomponentens förberedda pumpa": "den förberedda pumpan till huvudrätten",
        "huvudkomponentens yoghurt, olja, salt": "yoghurten, oljan och saltet till huvudrätten",
        "huvudkomponentens yoghurt, olja, senap och salt": "yoghurten, oljan, senapen och saltet till huvudrätten",
        "huvudkomponentens övriga smaksättare": "resten av smaksättningen till korven",
        "huvudkomponentens ost": "osten till korven",
        "som en bredbar huvudkomponent ": "",
        "till huvudkomponenten": "till rätten",
        "så att huvudkomponenten inte blir vattnig": "så att linsröran inte blir vattnig",
        "Fördela huvudkomponenten på omelettarken": "Fördela kycklingfyllningen på omelettarken",
        "Fördela huvudkomponenten och nudlarna på omelettarken": "Fördela tofufyllningen och nudlarna på omelettarken",
        "Fördela den varma huvudkomponenten över de frasiga nudelnästena": "Fördela den varma kycklingen med grönsaker och sås över de frasiga nudelnästena",
        "Servera huvudkomponenten ovanpå": "Servera kikärtsröran ovanpå",
        "Fyll pannkakorna med huvudkomponenten": "Fyll pannkakorna med den tillagade fyllningen",
        "vänd ner det i huvudkomponenten": "vänd ner det i fyllningen",
        "Blötläggningsvattnet hälls bort i nästa aktiva steg.": "Häll bort blötläggningsvattnet när kikärtorna har blötlagts klart.",
        "Kokspadet hälls bort; förlusten är okänd.": "Häll bort kokspadet.",
        "Kontrollera undersidan i nästa aktiva steg; förläng vid behov.": "Kontrollera därefter undersidan och grädda längre om det behövs.",
        "det angivna potatis-, gryn- eller brödtillbehöret": {
            "potatis": "potatisen", "ris": "riset", "bröd": "brödet", "havreris": "havreriset", "korn": "kornet",
        }.get(recipe["design"]["side"], "tillbehöret"),
        "senapen från fästkomponenten": "senapen till paneringen",
    }
    for before, after in replacements.items():
        text = text.replace(before, after)
    if re.search(r"huvudråvar|huvudkomponent|nästa aktiva steg|förlusten är okänd", text):
        raise ValueError((recipe["name"], "Unreviewed language", text))
    return re.sub(r" {2,}", " ", text).strip() if text != original else text


def rename_labels(row):
    for component in row["design"]["components"]:
        for amount in component["amounts"] or []:
            if amount["name"] == TAMARIND_LABEL:
                amount["name"] = "Tamarindkoncentrat CHS"
    return row


def rewrite_recipe(original, overrides):
    row = copy.deepcopy(original)
    if row["preparation"]["version"] == "smako-edible-input-v1":
        return row, []
    row["name"] = overrides.get(row["name"], row["name"])
    rename_labels(row)
    for step in row["design"]["steps"]:
        step["text"] = rewrite_step(step["text"], row, step)
    row["instructions"] = [step["text"] for step in row["design"]["steps"]]
    if row != original:
        row["design"]["batch_scaling"] = first.batch_basis(original)
    return row, []


def verify_pair(old, new, *, check_scaling=True):
    # Only the exact reviewed display label may differ; quantities, keys, units
    # and all preparation/loss metadata remain covered by the first verifier.
    normalized = old.model_validate(rename_labels(old.model_dump(mode="json")))
    first.verify_pair(normalized, new, check_scaling=check_scaling)


def checked_transition(review, *, check_scaling=False):
    return first.checked_transition(review, report=REPORT, rewriter=rewrite_recipe,
                                    pair_check=verify_pair, check_scaling=check_scaling)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--publish", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    options = {"report": REPORT, "rewriter": rewrite_recipe, "pair_check": verify_pair}
    if args.prepare:
        first.prepare(work=WORK, pack_prefix="recipe-language-followup-20261102", **options)
    elif args.publish:
        first.publish(work=WORK, **options)
    else:
        first.verify(**options)
