"""Allergens from the store's own product declaration.

Owner decision 2026-11-17: the stores' own allergen information is used for
allergy choices. Swedish/EU labelling names the fourteen allergen groups in
the ingredient list itself, so the store's published ingredient list is read
for them; City Gross also publishes a structured GS1 allergen list, which is
added on top. Matching is deliberately wide: a false match only removes a
product from a plan, a missed match could harm someone. Text after "kan
innehålla" and similar is a trace, everything else is present.
"""
from __future__ import annotations

import re
import unicodedata

# Every allergen choice the planner offers (values of personal_policy.ALLERGENS).
CHECKED = ("blötdjur", "fisk", "gluten", "jordnötter", "lupin", "mjölk", "nötter", "selleri",
           "senap", "sesam", "skaldjur", "soja", "sulfit", "vete", "ägg")

# Plant drinks, fats and spices whose names contain an allergen word but are not it.
_NOT = re.compile(
    r"kokos(?:mjölk|grädde|nöt\w*)|kakaosmör|sheasmör|muskotnöt\w*|bovete\w*|fri från \w+|utan \w+",
)
# A plant drink keeps its plant (oats are a gluten cereal) but is not milk.
_PLANT_DRINK = re.compile(r"(havre|ris|soja|mandel|cashew|ärt)(?:mjölk|grädde|dryck)")
_WORDS = {
    "mjölk": r"mjölk|grädd|smör|\w+ost\b|\bost(?!ron)|mozzarella|parmesan|cheddar|mascarpone|ricotta|keso|kvarg"
             r"|yoghurt|\bfil\b|filmjölk|kefir|vassle|kasein|laktos|lactose|crème fraiche|creme fraiche"
             r"|smetana|ghee|\bmilk|butter|cheese|whey|halloumi|kesella",
    "ägg": r"ägg|albumin|lysozym|\begg",
    "gluten": r"gluten|vete|durum|dinkel|spelt|råg|\bkorn\b|korn(?:mjöl|gryn|malt|flingor)|havre|kamut|emmer"
              r"|\bmalt\b|maltextrakt|maltmjöl|wheat|barley|\brye\b|\boats?\b|seitan|couscous|bulgur|mannagryn",
    "vete": r"vete|durum|dinkel|spelt|kamut|emmer|wheat|seitan|couscous|bulgur|mannagryn",
    "fisk": r"fisk|torsk|\blax|sej\b|kolja|sill|makrill|tonfisk|ansjovis|sardin|rödspätta|kummel|gädda|abborre"
            r"|\bgös|öring|röding|hälleflundra|pangasius|tilapia|strömming|skrei|fish|anchov|tuna|salmon|\bcod\b",
    "skaldjur": r"räk|kräft|krabb|hummer|langust|scampi|shrimp|prawn|crab|lobster|crayfish|skaldjur",
    "blötdjur": r"mussl|ostron|bläckfisk|snäck|sepia|calamar|octopus|\bsquid|mollus|blötdjur|escargot",
    "jordnötter": r"jordnöt|peanut|arachis",
    "nötter": r"mandel|hasselnöt|valnöt|cashew|pekan|paranöt|pistage|pistasch|macadamia|\bnötter"
              r"|almond|hazelnut|walnut|pecan|pistachio|nougat|marsipan|praliné",
    "soja": r"soja|\bsoy|edamame|tofu|tempeh|miso",
    "sesam": r"sesam|tahini|tahin",
    "selleri": r"selleri|celery|seller",
    "senap": r"senap|mustard",
    "lupin": r"lupin",
    "sulfit": r"sulfit|svaveldioxid|e ?22[0-8]\b|sulphit|sulfite|disulfit",
}
_PATTERNS = {name: re.compile(words) for name, words in _WORDS.items()}
_TRACE = re.compile(
    r"(kan innehålla|kan förekomma|spår av|may contain|tillverka\w* (?:i|på) \w+ (?:som|där)"
    r"|hanteras även|förpacka\w* i en|samma (?:linje|anläggning|fabrik))[^.]*",
)
# GS1 levelOfContainment as City Gross serialises it: 0 contains, 1 may contain.
_GS1_CONTAINS, _GS1_MAY_CONTAIN = 0, 1


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFC", text).casefold()
    return _PLANT_DRINK.sub(r"\1 ", _NOT.sub(" ", text))


def _found(text: str) -> set[str]:
    hits = {name for name, pattern in _PATTERNS.items() if pattern.search(text)}
    if "jordnötter" in hits and not _PATTERNS["nötter"].search(re.sub(r"jordnöt\w*", " ", text)):
        hits.discard("nötter")
    if "vete" in hits:
        hits.add("gluten")
    return hits


def usable_declaration(text) -> bool:
    """A store ingredient statement that can be read for allergens."""
    if not isinstance(text, str):
        return False
    words = re.findall(r"[a-zåäöéü]{2,}", text.casefold())
    return bool(words) and len(text) <= 5000


def declared_allergens(text, structured=None):
    """(checked, present, trace) from the store's declaration, or None if unusable."""
    if not usable_declaration(text):
        return None
    plain = _plain(text)
    traces = " ".join(match.group(0) for match in _TRACE.finditer(plain))
    present = _found(_TRACE.sub(" ", plain))
    trace = _found(traces) - present
    for row in structured or ():
        if not isinstance(row, dict):
            continue
        names = _found(_plain(str(row.get("typeCode") or "")))
        level = row.get("levelOfContainment")
        if level == _GS1_MAY_CONTAIN:
            trace |= names - present
        elif level is not None and level != _GS1_CONTAINS and not isinstance(level, bool) and level > _GS1_MAY_CONTAIN:
            continue  # "free from" and other declared absences add nothing
        else:
            present |= names
            trace -= names
    return CHECKED, tuple(sorted(present)), tuple(sorted(trace))
