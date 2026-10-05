"""Additional authored culinary constraints; never evidence of price or nutrition.

All ordinary product matching, amount, source and allergy gates still apply.
Unknown pack requirements fail closed. No recipe quantities are changed here.
"""
import re

PACK_KEYS = frozenset(["chicken_thigh", "chicken_breast", "cod", "salmon", "pork_mince", "tofu", "white_beans", "black_beans", "chickpeas", "tuna", "red_lentils", "rice", "pasta", "small_pasta", "couscous", "rice_noodles", "egg_noodles", "pita", "tortilla", "gnocchi", "flour", "potato", "carrot", "cabbage", "onion", "red_onion", "garlic", "ginger", "cucumber", "tomato", "pepper", "mushroom", "spinach", "peas", "corn", "broccoli", "cauliflower", "apple", "crushed_tomato", "tomato_paste", "olives", "yogurt", "creme_fraiche", "feta", "cottage_cheese", "hard_cheese", "milk", "egg", "coconut_milk", "lemon_juice", "lime_juice", "oil", "soy_sauce", "mustard", "peanut_butter", "peanuts", "sugar", "oregano", "basil", "dill", "parsley", "cumin", "paprika_powder", "smoked_paprika", "turmeric", "coriander_seed", "chili", "salt", "black_pepper"])


def compatible(keys, product, fact):
    if not set(keys) <= PACK_KEYS:
        return False
    text = product.name.casefold()
    composition = " ".join(fact.ingredients).casefold() if fact else ""
    rules = {
        "chicken_thigh": r"kyckling\s*lårfilé", "chicken_breast": r"kyckling\s*(?:bröst)?filé|kycklingbröst",
        "cod": r"torsk(?:filé|rygg)?", "pork_mince": r"fläskfärs", "small_pasta": r"risoni|kritharaki|orzo",
        "pasta": r"penne|fusilli|makaroner|rigatoni|farfalle|orecchiette",
        "rice_noodles": r"risnudlar", "egg_noodles": r"äggnudlar", "pita": r"pitabröd",
        "tortilla": r"vete", "gnocchi": r"gnocchi", "peanuts": r"jordnötter",
    }
    for key in keys:
        if key in rules and not re.search(rules[key], text + (" " + composition if key == "tortilla" else "")):
            return False
        if key == "chicken_breast" and re.search(r"lår|inner", text):
            return False
        if key == "tuna" and ("vatten" not in text + composition or re.search(r"olja|tomat|chili", text + composition)):
            return False
        if key == "couscous" and re.search(r"pärl|israel", text):
            return False
        if key == "basil" and re.search(r"fryst|djupfryst", text + " " + (product.category or "")):
            return False
        if key == "mustard" and re.search(r"grov|skånsk|kornig", text):
            return False
        if key == "chili" and not re.search(r"\b(?:mild|medium|medel)\b", text + " " + composition):
            # Authored mild/medium flakes are not arbitrary hot chili. A name
            # synonym alone supplies neither heat nor a substitute quantity.
            return False
        if key == "paprika_powder" and not re.search(r"\b(?:mild|milt|söt|sweet)\b", text + " " + composition):
            return False
        if key == "black_pepper" and not re.search(r"\b(?:malen|finmalen|mald|ground)\b", text + " " + composition):
            return False
        if key == "spinach" and not re.search(r"\b(?:hackad|finhackad|hackat|chopped)\b", text + " " + composition):
            return False
        if key == "peanuts" and ("rostade" not in text + composition or "osaltade" not in text or re.search(r"\bsalt\b", composition)):
            return False
        if key == "gnocchi" and ("potatis" not in composition or re.search(r"fylld|spenat|ost|pesto|sås", text)):
            return False
        if key in {"cottage_cheese", "creme_fraiche"}:
            match = re.search(r"(\d+(?:[,.]\d+)?)\s*%", text)
            fat = float(match[1].replace(",", ".")) if match else (
                fact.nutrition.get("fat_g") if fact and fact.nutrition_unit == "g" and fact.nutrition_preparation == "as_sold" else None)
            low, high = (1, 4) if key == "cottage_cheese" else (12, 34)
            if fat is None or not low <= fat <= high:
                return False
    return True


def additional_whole_identity(canonical, form, label, composition):
    """Exact plain identities absent from the earlier complete-dinner library.

    The caller has stripped only the published brand and package amount. A
    culinary label alone never supplies a missing declaration or mass basis.
    """
    patterns = {
        "svartpeppar": ("dry", r"(?:malen )?svartpeppar(?: malen| finmalen| burk)*"),
        "rökt paprikapulver": ("dry", r"(?:rökt paprikapulver|paprikapulver rökt)(?: milt| mild| burk)*"),
        "malen koriander": ("dry", r"(?:malen koriander|koriander malen)(?: burk)*"),
        "chiliflakes": ("dry", r"(?:chiliflakes|chili flakes|chiliflingor)(?: mild| medium| medel| burk| påse| eko)*"),
        "strösocker": ("dry", r"strösocker(?: ekologiskt| eko)*"),
        "äpple": ("raw_edible", r"(?:äpple|äpplen)(?: röda| gröna| svenska| ekologiska| klass [12])*"),
        "jordnötter": ("as_sold", r"(?:rostade )?jordnötter(?: rostade| osaltade)*"),
        "tonfisk": ("cooked_drained", r"tonfisk(?: i vatten| bitar| skipjack)*"),
        "gnocchi": ("as_sold", r"(?:potatisgnocchi|gnocchi)(?: di patate| potatis| naturell| original)*"),
    }
    entry = patterns.get(canonical)
    if entry is None or form != entry[0] or not re.fullmatch(entry[1], label):
        return False
    return not (canonical in {"svartpeppar", "rökt paprikapulver", "malen koriander", "chiliflakes"} and re.search(r"\b(?:salt|socker|lök|vitlök|senap|selleri|olja)\b", composition.split("kan innehålla")[0]))
