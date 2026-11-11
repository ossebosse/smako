"""Which products a generic shopping-list row ("banan", "kaffe") may be bought as.

A generic row used to accept every product whose name merely contained the
typed words, so "banan" was bought as banana yoghurt and "smör" as butter
flavoured popcorn. A row is now a product only when the word names the goods:

* the word is in the product name as its own word (plural and definite forms
  count, and a few listed compounds such as bryggkaffe for kaffe);
* it is not a flavour or a part of a mix ("med smör", "banan & vanilj");
* and the store's own category agrees. A category that names the goods
  accepts the product. A specific category that does not, rejects it. The same
  product in another chain shares that evidence through its GTIN or its exact
  name and brand. Where only broad categories exist ("Skafferi"), the word
  must be the first or last word of the name.

Nothing here prices or ranks a product, and exact product choices do not pass
through this filter. Recipes keep their own reviewed product links.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

VERSION = "generic-items-v1"

_TOKEN = re.compile(r"[a-z0-9]+|&|,|/")
_SEPARATORS = frozenset({"&", ",", "/"})
# Endings that keep a Swedish noun the same goods: banan/bananer, ägg/äggen.
_ENDINGS = frozenset({"", "er", "ar", "or", "n", "en", "et", "r", "ter", "s", "na", "erna", "arna", "orna"})
# The word after these is a flavour or an ingredient, not the goods.
_FLAVOUR_BEFORE = frozenset({"med", "smak", "smaksatt", "av", "och", "i", "a", "till", "for", "pa", "utan", *_SEPARATORS})
_LIST_AFTER = frozenset({"och", *_SEPARATORS})
# Words that may stand before the goods without changing what it is.
_LEADING = frozenset(
    "ekologisk ekologiska ekologiskt eko krav svensk svenska svenskt farsk farska farskt fryst frysta "
    "glutenfri glutenfritt laktosfri laktosfritt mini stor stora liten sma extra original klassisk "
    "naturell vegansk kokt kokta torkad torkade hel hela mald malet fast mjolig rod roda gul gula gron "
    "grona vit vita svart svarta ny nya sot sota fin fina grov grova mild lagrad".split()
)
_PACK = re.compile(r"^\d+(p|pack|st|g|kg|ml|cl|l|dl)?$|^(pack|st|klass|styck|kg|g|ml|l|eko|krav|ca)$")
# Compounds that are the same goods as their last part. Other compounds are
# other goods: jordnötssmör is not smör and kokosmjölk is not mjölk.
_COMPOUNDS = {
    "kaffe": {"bryggkaffe", "kokkaffe", "snabbkaffe", "bonkaffe", "espressokaffe"},
    "mjolk": {"mellanmjolk", "lattmjolk", "standardmjolk", "minimjolk", "helmjolk"},
    "fars": {"notfars", "blandfars", "flaskfars", "kycklingfars", "hogrevsfars"},
    "ris": {"jasminris", "basmatiris"},
    "ost": {"hushallsost", "prastost", "herrgardsost", "greveost", "hardost"},
    "gradde": {"vispgradde", "matlagningsgradde", "mellangradde"},
    "juice": {"apelsinjuice", "appeljuice"},
    "socker": {"strosocker"},
    "mjol": {"vetemjol"},
    "olja": {"rapsolja", "olivolja"},
    "brod": {"formbrod", "rostbrod", "lantbrod"},
    "fil": {"filmjolk", "mellanfil", "lattfil"},
    "potatis": {"matpotatis"},
}
# Cuts and forms of the same goods: lax is also laxfilé and laxbitar.
_CUTS = frozenset("file fileer filer bitar portioner sida rygg ryggfile lar larfile brost brostfile vingar klubbor".split())
_CURATED = {
    row["query"].casefold(): row
    for row in json.loads((Path(__file__).parents[1] / "data/shopping_generics.json").read_text(encoding="utf8"))
}


def _curated(query: str) -> dict | None:
    """The reviewed generic a typed name means, also in plural: tomater is the row for tomat."""
    key = query.strip().casefold()
    if key in _CURATED:
        return _CURATED[key]
    words = _goods_words(query)
    if len(words) != 1:
        return None
    for row in _CURATED.values():
        names = _words(row["query"]) + _words(row["name"])
        if len(_words(row["query"])) == 1 and any(same_word(words[0], name) for name in names):
            return row
    return None


@lru_cache(maxsize=65536)
def _fold(value: str) -> str:
    text = unicodedata.normalize("NFKD", (value or "").casefold())
    return "".join(c for c in text if not unicodedata.combining(c))


@lru_cache(maxsize=65536)
def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_TOKEN.findall(_fold(value).replace("-", " ")))


def _words(value: str) -> tuple[str, ...]:
    return tuple(t for t in _tokens(value) if t not in _SEPARATORS)


def _goods_words(query: str) -> tuple[str, ...]:
    """The words of a generic that name goods; amounts and percentages are properties."""
    return tuple(w for w in _words(query) if not w[0].isdigit())


def same_word(first: str, second: str) -> bool:
    """The same noun in another number or form, never another word."""
    if first == second:
        return True
    short, long = (first, second) if len(first) <= len(second) else (second, first)
    if len(short) >= 3 and long.startswith(short) and long[len(short):] in _ENDINGS:
        return True
    if len(short) >= 4 and short[-1] == "a" and long in {short[:-1] + "or", short[:-1] + "orna"}:
        return True
    return len(short) >= 4 and short[-1] == "e" and long in {short[:-1] + "ar", short[:-1] + "arna"}


def word_forms(query: str) -> tuple[str, ...]:
    """Search words for the last word of a generic: its base forms and listed compounds."""
    words = _goods_words(query)
    if not words:
        return ()
    head = words[-1]
    forms = {head}
    for ending in sorted(_ENDINGS - {""}, key=len, reverse=True):
        if head.endswith(ending) and len(head) - len(ending) >= 3:
            forms.add(head[: -len(ending)])
    if head.endswith("or") and len(head) >= 5:
        forms.add(head[:-2] + "a")
    if head.endswith("ar") and len(head) >= 5:
        forms.add(head[:-2] + "e")
    for base in tuple(forms):
        forms.update(_COMPOUNDS.get(base, ()))
        forms.update(base + cut for cut in ("file", "bitar"))
    return tuple(sorted(forms))


def _head_matches(head: str, token: str) -> bool:
    if len(head) >= 3 and token.startswith(head) and token[len(head):] in _CUTS:
        return True
    return same_word(head, token) or token in _COMPOUNDS.get(head, ()) or any(
        same_word(head, base) and token in compounds for base, compounds in _COMPOUNDS.items())


def _name_role(query: str, name: str, brand: str | None) -> str | None:
    """None: the words are not in the name. Otherwise flavour, core or mention."""
    wanted = _goods_words(query)
    if not wanted:
        return "core"  # nothing but numbers to go on; the planner's own checks decide
    tokens = _tokens(name)
    words = [t for t in tokens if t not in _SEPARATORS]
    brand_words = set(_words(brand or ""))
    if set(wanted) <= brand_words:
        return "core"  # the row names the brand itself
    if any(not any(same_word(word, t) for t in (*words, *brand_words)) for word in wanted[:-1]):
        return None
    head = wanted[-1]
    hits = [i for i, t in enumerate(tokens) if _head_matches(head, t)]
    if not hits:
        return None
    modifiers = set(wanted[:-1])
    role = "flavour"
    for i in hits:
        before = tokens[i - 1] if i else None
        after = tokens[i + 1] if i + 1 < len(tokens) else None
        if before in _FLAVOUR_BEFORE and before not in modifiers:
            continue
        if after in _LIST_AFTER:
            continue
        lead = [t for t in tokens[:i] if t not in _SEPARATORS]
        tail = [t for t in tokens[i + 1:] if t not in _SEPARATORS and not _PACK.match(t)]
        first = all(t in _LEADING or t in brand_words or any(same_word(m, t) for m in modifiers) for t in lead)
        if first or not tail:
            return "core"
        role = "mention"
    return role


def _category_names(head: str, category: str) -> bool:
    for token in _words(category):
        if _head_matches(head, token):
            return True
        # "Bryggkaffe" names kaffe, and "Gryn" names havregryn.
        if len(token) > len(head) + 1 and token.endswith(head):
            return True
        if len(token) >= 3 and len(head) > len(token) + 1 and (head.endswith(token) or (len(token) >= 5 and head.startswith(token))):
            return True
    return False


class GenericItemIndex:
    """Category evidence shared between the rows of one product. Built once per price data."""

    def __init__(self, prepared):
        self.products = prepared.universe.products
        by_identity, by_label = defaultdict(list), defaultdict(set)
        for position, product in enumerate(self.products):
            label = _fold(product.brand or "") + "|" + _fold(product.name)
            identity = product.gtin or label
            by_identity[identity].append(position)
            by_label[label].add(identity)
        self._by_identity = dict(by_identity)
        self._by_label = dict(by_label)
        self._chain_rows = Counter(p.chain or p.store_id for p in self.products)
        self._category_rows = Counter((p.chain or p.store_id, p.category) for p in self.products)

    def _specific(self, product) -> bool:
        """A category narrow enough to say what the goods are.

        A path ("Frukt > Bananer") is narrow. A single name is narrow when it
        holds a small part of a full assortment, as Coop's leaf categories do;
        "Skafferi" or "Mejeri, ost & ägg" say too little to reject a product.
        """
        category = product.category or ""
        if not category or _fold(category) == "okategoriserad":
            return False
        if " > " in category:
            return True
        chain = product.chain or product.store_id
        total = self._chain_rows[chain]
        return total >= 500 and self._category_rows[chain, category] / total < 0.02

    def _related(self, position):
        product = self.products[position]
        label = _fold(product.brand or "") + "|" + _fold(product.name)
        seen = set()
        for identity in {product.gtin or label, *self._by_label.get(label, ())}:
            seen.update(self._by_identity.get(identity, ()))
        return seen

    def reason(self, query: str, position: int) -> str | None:
        """None when the product is the generic; otherwise why it is not."""
        product = self.products[position]
        role = _name_role(query, product.name, product.brand)
        if role is None:
            return "the words are not in the product name"
        if role == "flavour":
            return "the word is a flavour or one part of a mix"
        curated = _curated(query)
        if curated:
            words = _words(product.name)
            if any(same_word(_fold(excluded), w) for excluded in curated.get("exclude", ()) for w in words):
                return "a prepared or preserved form the generic does not ask for"
        wanted = _goods_words(query)
        if not wanted:
            return None
        head = wanted[-1]
        if set(wanted) & set(_words(product.brand or "")):
            # The row names a brand ("coca cola", "zoégas skånerost"); the
            # store's category is named after the goods, not the brand.
            return None
        related = [self.products[i] for i in self._related(position)]
        if any(_category_names(head, p.category) for p in related):
            return None
        if any(self._specific(p) for p in related):
            return "the store's category is for other goods"
        return None if role == "core" else "the word is not what the product is called"

    def accepts(self, query: str, position: int) -> bool:
        return self.reason(query, position) is None

    def closeness(self, query: str, position: int) -> int:
        """Fewer extra words is closer to the plain goods; used only to order equal prices."""
        wanted = _goods_words(query)
        words = [w for w in _words(self.products[position].name) if not _PACK.match(w)]
        return sum(1 for w in words if not any(same_word(q, w) or _head_matches(q, w) for q in wanted))


def generic_item_index(prepared) -> GenericItemIndex:
    return prepared.product_search_cache.get_or_compute("generic-item-index:" + VERSION, lambda: GenericItemIndex(prepared))


def generic_search_positions(prepared, query: str) -> frozenset[int]:
    """Rows to consider for a generic: the plain search plus other forms of its last word."""
    from app.services.meal_prepared_artifacts import ingredient_search_positions

    positions = set(ingredient_search_positions(prepared, query, complete=False))
    words = _goods_words(query)
    if words:
        modifiers = " ".join(words[:-1])
        for form in word_forms(query):
            if form != words[-1]:
                positions.update(ingredient_search_positions(prepared, f"{modifiers} {form}".strip(), complete=False))
    return frozenset(positions)


def usual_amount(prepared, query: str) -> dict | None:
    """The package size most products of this generic are sold in, for a one-tap add."""
    index = generic_item_index(prepared)
    sizes = Counter()
    for position in generic_search_positions(prepared, query):
        product = index.products[position]
        if not (product.package_quantity and product.package_unit in {"g", "ml", "st"}):
            continue
        if not index.accepts(query, position):
            continue
        if str(getattr(product.sale_model, "value", product.sale_model)) in {"sold_by_weight", "variable_weight_package"}:
            # Loose goods have no package; half a kilo is the usual first amount.
            sizes[(500.0, "g")] += 1
        else:
            sizes[(float(product.package_quantity), product.package_unit)] += 1
    if not sizes:
        return None
    (quantity, unit), _count = max(sizes.items(), key=lambda row: (row[1], -row[0][0]))
    return {"quantity": quantity, "unit": unit}
