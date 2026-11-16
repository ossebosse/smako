"""Words for the shopping and pantry search (step 5, 2026-11-15).

Only the search people see uses this (ProductSearchIndex.search). The
retrieval that recipes and baskets use (ProductSearchIndex.retrieve) is
unchanged, so nothing here can make a product eligible for a recipe.

All words are in search_text form (lower case, å/ä/ö folded to a/o).
"""

from __future__ import annotations

# Two spellings of the same word, also at the end of a compound word
# ("isbergssallat" is "isbergssallad"). Reviewed by hand.
SPELLINGS = (("sallat", "sallad"), ("arter", "artor"))

# A word people search for and the words shops use for the same food.
SYNONYMS = {
    "vindruvor": ("druvor", "druva"),
    "vindruva": ("druvor", "druva"),
    "druvor": ("druva",),
    "kottfars": ("blandfars", "notfars", "flaskfars"),
    "frysta": ("fryst", "frysta"),
    "fryst": ("frysta",),
    "isbergssallad": ("isberg",),
    "soppasar": ("avfallspase", "sopsack", "soppase"),
    "soppase": ("avfallspase", "sopsack"),
    "sopsackar": ("sopsack", "avfallspase"),
}

# Compound words that only look as if they end in the searched word.
NOT_COMPOUNDS = {"ost": frozenset({"frukost", "kompost"}), "ris": frozenset({"pris", "kris"}),
                 "lax": frozenset({"relax"}), "agg": frozenset({"lagg", "bagg"})}

# Pet and baby products are shown only when the search asks for them.
PET_WORDS = frozenset({"hund", "katt", "hundmat", "kattmat", "djur", "djurmat", "husdjur", "kattsand",
                       "hundgodis", "kattgodis", "valp", "kattunge", "fagelfro", "fagelmat", "kanin", "gnagare"})
BABY_WORDS = frozenset({"barn", "barnmat", "bebis", "baby", "valling", "klammis", "barngrot",
                        "modersmjolksersattning", "ersattning", "smabarn", "blojor", "napp", "nappar"})


def spellings(word: str) -> set[str]:
    """The word and its other spelling, also as the last part of a compound."""
    out = {word}
    for a, b in SPELLINGS:
        for x, y in ((a, b), (b, a)):
            if word.endswith(x):
                out.add(word[: len(word) - len(x)] + y)
    return out


def alternatives(word: str) -> set[str]:
    out = set()
    for spelled in spellings(word):
        out.add(spelled)
        for synonym in SYNONYMS.get(spelled, ()):
            out |= spellings(synonym)
    return out


def asks_for_pets(words) -> bool:
    return any(w in PET_WORDS or w.startswith(("hund", "katt")) for w in words)


def asks_for_babies(words) -> bool:
    return any(w in BABY_WORDS or w.startswith(("barn", "bebis", "baby")) for w in words)


def is_audience_word(word: str) -> bool:
    """A word that says who the product is for (dog, cat, baby) rather than what it is."""
    return asks_for_pets([word]) or asks_for_babies([word])
