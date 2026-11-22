"""Members' recipe ratings and points for receipts (owner request 2026-11-22).

"Medlemmar ska kunna gilla och ogilla recept. Och man ska kunna se
gillningar/ogillningar i varje recept. Man ska som medlem kunna få poäng i
Smako. Det får man om man skannar sitt kvitto efter att ha handlat
inköpslistan. Extra poäng om priset inte matchar, eller inte finns i
varuunderlaget för Smako."

Ratings are per dish (the design base, so every variant of a dish shares
them). A member's liked dishes are preferred and disliked dishes never
proposed in the member's own plans (owner choice 2026-11-22).

A receipt is read on the member's phone (photo, OCR in the browser) or from a
PDF (text extracted here); only the confirmed text lines are kept, never the
picture. Points (planning_rules, admin tab "Matplanering"; owner decision 2026-11-22:
the items need not be on the shopping list):
  * receipt_points for a receipt with at least receipt_min_list_items lines,
  * receipt_price_points per line whose product Smako has at that store at
    another price,
  * receipt_missing_points per line Smako has no product for at that store,
    or every line of a store without Smako prices,
  at most receipt_max_points per receipt.
"""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import unicodedata
from datetime import UTC, date, datetime, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS member_recipe_ratings (
    owner TEXT NOT NULL,
    base_id TEXT NOT NULL,
    value INTEGER NOT NULL CHECK (value IN (-1, 1)),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (owner, base_id)
);
CREATE INDEX IF NOT EXISTS ix_member_recipe_ratings_base ON member_recipe_ratings(base_id);
CREATE TABLE IF NOT EXISTS member_receipts (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    created_at TEXT NOT NULL,
    plan_id TEXT,
    store_text TEXT NOT NULL,
    store_known INTEGER NOT NULL,
    purchased_on TEXT,
    fingerprint TEXT NOT NULL UNIQUE,
    lines_json TEXT NOT NULL,
    points INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_member_receipts_owner ON member_receipts(owner, created_at);
CREATE TABLE IF NOT EXISTS member_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner TEXT NOT NULL,
    created_at TEXT NOT NULL,
    points INTEGER NOT NULL,
    reason TEXT NOT NULL,
    receipt_id TEXT
);
CREATE INDEX IF NOT EXISTS ix_member_points_owner ON member_points(owner, created_at);
"""

BASE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,159}$")


class RewardError(ValueError):
    """A request the member can fix; the message is shown as is."""


def _now():
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------- ratings

def rate(store, owner, base_id, value):
    """value 1 (gillar), -1 (ogillar) or 0 (ångra)."""
    if not BASE_ID.match(base_id or ""):
        raise RewardError("Okänt recept.")
    if value not in (-1, 0, 1):
        raise RewardError("Välj gilla eller ogilla.")
    with store._connect() as db:
        if value == 0:
            db.execute("DELETE FROM member_recipe_ratings WHERE owner=? AND base_id=?", (owner, base_id))
        else:
            db.execute("""INSERT INTO member_recipe_ratings VALUES (?, ?, ?, ?)
                ON CONFLICT(owner, base_id) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                       (owner, base_id, value, _now()))


def ratings(store, base_ids, owner=None):
    """Likes and dislikes for each dish, and the member's own choice."""
    ids = [b for b in dict.fromkeys(base_ids) if BASE_ID.match(b or "")][:60]
    result = {b: {"likes": 0, "dislikes": 0, "mine": 0} for b in ids}
    if not ids:
        return result
    marks = ",".join("?" * len(ids))
    with store._connect() as db:
        for row in db.execute(f"""SELECT base_id, SUM(value = 1) AS likes, SUM(value = -1) AS dislikes
                                  FROM member_recipe_ratings WHERE base_id IN ({marks}) GROUP BY base_id""", ids):
            result[row["base_id"]].update(likes=row["likes"], dislikes=row["dislikes"])
        if owner:
            for row in db.execute(f"""SELECT base_id, value FROM member_recipe_ratings
                                      WHERE owner=? AND base_id IN ({marks})""", (owner, *ids)):
                result[row["base_id"]]["mine"] = row["value"]
    return result


def member_choices(store, owner):
    """(liked, disliked) dish base ids, newest first."""
    import sqlite3

    try:
        with store._connect() as db:
            rows = db.execute("""SELECT base_id, value FROM member_recipe_ratings WHERE owner=?
                                 ORDER BY updated_at DESC LIMIT 1000""", (owner,)).fetchall()
    except sqlite3.OperationalError:  # a store without the member tables
        return [], []
    return ([r["base_id"] for r in rows if r["value"] == 1], [r["base_id"] for r in rows if r["value"] == -1])


# ---------------------------------------------------------------- receipts

_PRICE = re.compile(r"(-?\d{1,5}[,.]\d{2})\s*(?:kr|sek|[a-z*]{0,2})?\s*$", re.IGNORECASE)
_SKIP = re.compile(r"\b(?:papperskasse|bärkasse|plastkasse|kasse|pant|total|totalt|summa|att betala|moms|netto|brutto|kort|kontant|växel|betal|bank|visa|"
                   r"mastercard|swish|kvitto|org\.?\s*nr|tel|öppet|tack|spara|bonus|poäng|avrundning|"
                   r"erhållen|varav|exkl|inkl)\b", re.IGNORECASE)
_DISCOUNT = re.compile(r"\b(?:rabatt|rab|erbjudande|kampanj|pant retur|medlemspris|mängdrabatt|\d+\s*för)\b", re.IGNORECASE)
_QTY = re.compile(r"(\d+(?:[,.]\d+)?)\s*(st|kg|g)\s*[x*à@]\s*(\d+[,.]\d{2})", re.IGNORECASE)
_DATE = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b|\b(\d\d)[./-](\d\d)[./-](20\d\d|\d\d)\b")
CHAINS = (("ica", r"\bica\b"), ("coop", r"\bcoop\b"), ("willys", r"\bwillys\b"), ("hemköp", r"\bhemk[oö]p\b"),
          ("lidl", r"\blidl\b"), ("city gross", r"\bcity\s*gross\b"), ("netto", r"\bnetto\b"),
          ("tempo", r"\btempo\b"), ("mathem", r"\bmathem\b"))


def _number(text):
    return float(text.replace(",", "."))


def fold(text):
    text = unicodedata.normalize("NFKC", str(text or "")).casefold()
    return re.sub(r"[^0-9a-zåäöéü]+", " ", text).strip()


def parse_receipt(text):
    """Store, date and bought lines of a receipt's text (OCR or PDF)."""
    raw = [line.strip() for line in str(text or "").replace("\r", "\n").split("\n")]
    raw = [line for line in raw if line][:400]
    if not raw:
        raise RewardError("Vi hittade ingen text på kvittot. Ta en skarpare bild i bra ljus.")
    header = " ".join(raw[:8])
    chain = next((name for name, pattern in CHAINS if re.search(pattern, fold(" ".join(raw[:12])))), None)
    store_text = next((line for line in raw[:8] if chain and re.search(dict(CHAINS)[chain], fold(line))), raw[0])[:120]
    purchased_on = None
    for line in raw:
        m = _DATE.search(line)
        if m:
            try:
                if m.group(1):
                    purchased_on = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                else:
                    year = int(m.group(6)); year += 2000 if year < 100 else 0
                    purchased_on = date(year, int(m.group(5)), int(m.group(4)))
                break
            except ValueError:
                continue
    lines, ended = [], False
    pending = None  # a quantity line whose item has not been read yet
    letters = re.compile(r"[A-Za-zÅÄÖåäö]{3}")

    def explains(qty, row):
        # "1,015 kg x 24,45 = 24,82" belongs to the item that cost 24,82.
        # "TONFISK 14,50 / 2 st x 14,50 = 29,00" belongs to the item priced 14,50.
        return abs(qty["total"] - row["price"]) <= 0.05 or abs(qty["unit_price"] - row["price"]) <= 0.05

    for line in raw:
        folded = fold(line)
        if re.match(r"^(?:totalt?|summa|att betala)\b", folded):
            ended = True
        if ended:
            continue
        quantity = _QTY.search(line)
        price = _PRICE.search(line)
        if quantity and price and price.start() < quantity.end():
            price = None  # "5 st x 12,25": the unit price is not a line price
        if quantity and not letters.search(_QTY.sub("", line[:price.start()] if price else line)):
            # A quantity line ("0,532 kg x 29,90  15,91"). Receipts print it under
            # or over its item and OCR can change the order: it belongs to the
            # neighbouring item whose price it explains.
            qty = {"quantity": _number(quantity.group(1)), "unit": quantity.group(2).lower(),
                   "unit_price": _number(quantity.group(3))}
            qty["total"] = _number(price.group(1)) if price else round(qty["quantity"] * qty["unit_price"], 2)
            if lines and (explains(qty, lines[-1]) or "quantity" not in lines[-1] and lines[-1].get("unpriced")):
                lines[-1].update({k: v for k, v in qty.items() if k != "total"}, price=qty["total"])
                lines[-1].pop("unpriced", None)
            else:
                pending = qty
            continue
        if not price:
            # A weighed item's name stands alone; its weight line follows.
            if letters.search(line) and not _SKIP.search(line) and not _DATE.search(line):
                if lines and lines[-1].get("unpriced"):
                    lines.pop()
                lines.append({"description": line.strip(" .:*-\t")[:120], "price": 0.0, "unpriced": True})
            continue
        value = _number(price.group(1))
        description = line[:price.start()].strip(" .:*-\t")
        if _SKIP.search(line) or not re.search(r"[A-Za-zÅÄÖåäö]{2}", description) and not quantity:
            continue
        if lines and lines[-1].get("unpriced") and not quantity:
            lines.pop()  # a header or note line, not an item waiting for its weight
        if (value < 0 or _DISCOUNT.search(description)) and lines:
            lines[-1]["price"] = round(lines[-1]["price"] - abs(value), 2)
            lines[-1]["discount"] = True
            continue
        if value <= 0 or value > 5000:
            continue
        row = {"description": _QTY.sub("", description).strip()[:120] or description[:120], "price": value}
        if quantity:
            row.update(quantity=_number(quantity.group(1)), unit=quantity.group(2).lower(),
                       unit_price=_number(quantity.group(3)))
        elif pending and explains(pending, row):
            row.update({k: v for k, v in pending.items() if k != "total"})
        pending = None
        lines.append(row)
    lines = [{k: v for k, v in l.items() if k != "unpriced"} for l in lines if l["price"] > 0][:80]
    if not lines:
        raise RewardError("Vi kunde inte läsa några varor på kvittot. Fota hela kvittot rakt uppifrån.")
    return {"store_text": store_text, "chain": chain, "purchased_on": purchased_on.isoformat() if purchased_on else None,
            "lines": lines, "header": header[:200]}


_STOP = {"eko", "ekologisk", "ekologiska", "krav", "svensk", "svenska", "sverige", "st", "g", "kg", "ml", "cl", "l", "p",
         "pack", "förp", "ca", "nat", "och", "med", "i", "av", "fryst", "färsk", "garant", "ica", "coop", "eldorado",
         "xtra", "änglamark", "hemköp", "willys", "large", "medium", "small", "ute", "inne"}


def _tokens(text):
    folded = fold(re.sub(r"\[\d+\]", " ", text)).translate(str.maketrans("éèêü", "eeeu"))  # RYGGFILE = Ryggfilé
    return [t for t in folded.split() if len(t) >= 2 and not t.isdigit()]


_SIZE = re.compile(r"(\d+(?:[,.]\d+)?)\s*(kg|g|ml|cl|l|p|st|%)(?![a-zåäö])", re.IGNORECASE)
# Receipt shorthand for the words product names use.
# Inflection endings: "TOMATER" is tomat, "BABYDRY" is not baby.
_ENDINGS = frozenset({"", "a", "e", "n", "r", "s", "t", "ar", "er", "or", "na", "en", "et", "ad", "ade", "arna", "erna"})
_RECEIPT_WORDS = {"ute": "utomhus", "inne": "inomhus", "eko": "ekologisk", "nat": "naturell", "krossad": "krossade"}
_CONFLICTS = (({"ute", "utomhus"}, {"inomhus", "inne"}), ({"laktosfri", "laktosfritt"}, None), ({"fryst", "frysta"}, None))


def sizes(text):
    """{kind: value} for sizes named in a text: weight in g, volume in ml, pieces, percent."""
    found = {}
    for number, unit in _SIZE.findall(str(text or "")):
        value, unit = float(number.replace(",", ".")), unit.casefold()
        kind, value = {"kg": ("g", value * 1000), "g": ("g", value), "l": ("ml", value * 1000), "cl": ("ml", value * 10),
                       "ml": ("ml", value), "p": ("st", value), "st": ("st", value), "%": ("%", value)}[unit]
        found.setdefault(kind, value)
    return found


def _similarity(receipt, product, product_sizes=None, brand=""):
    """How well a receipt line names a product, 0..1.

    Each receipt word must start a product word (receipts abbreviate:
    "NAT" for naturell). Generic words (eko, svensk...) never make a match on
    their own. A size on the receipt (900G, 18P, 40%) must agree with the
    product's, and opposite words (ute/inomhus) rule a product out.
    """
    words = [_RECEIPT_WORDS.get(w, w) for w in _tokens(_SIZE.sub(" ", receipt)) if not w.isdigit()]
    names = _tokens(_SIZE.sub(" ", f"{product} {brand or ''}"))  # "HEINZ KETCHUP": the brand counts
    names += [a + b for a, b in zip(names, names[1:])]  # "BABYDRY" = Baby Dry
    if not words or not names:
        return 0.0
    # A receipt word starts a product word ("NAT" naturell, "POTATIS" potatisar),
    # differs from it by an ending ("TOMATER" tomat), or ends a compound when the
    # receipt names the rest ("POTATIS BAK" bakpotatis). "PÄRONSPLIT" is not päron.
    def found(w):
        for n in names:
            if n.startswith(w) and (len(w) <= 4 or len(n) - len(w) <= 4):
                return True
            if len(n) >= 4 and w.startswith(n) and w[len(n):] in _ENDINGS:
                return True
            if len(w) >= 4 and n.endswith(w) and (len(w) >= 6 or any(n.startswith(o) for o in words if o != w and len(o) >= 3)):
                return True
        return False
    if not any(len(w) >= 3 and w not in _STOP and found(w) for w in words):
        return 0.0
    for left, right in _CONFLICTS:
        has_left = bool(left & set(words)) , bool(left & set(names))
        if right is None:
            if has_left[0] != has_left[1]:
                return 0.0
        elif (left & set(words) and right & set(names)) or (right & set(words) and left & set(names)):
            return 0.0
    content = [w for w in words if w not in _STOP] or words  # generic words neither help nor hurt
    # Receipts start with the food ("GURKA EKO ST", "ZUCCHINI GRÖN"): the first
    # word must match, so a describing word ("grön") cannot carry a match.
    if not found(content[0]) and len(content) > 1 and not found(content[1]):
        return 0.0
    if not found(content[0]) and len(content[0]) >= 4:
        return 0.0
    # The first word names the food and weighs double; the others describe it.
    score = (2 * found(content[0]) + sum(found(w) for w in content[1:])) / (len(content) + 1)
    wanted, have = sizes(receipt), {**sizes(product), **(product_sizes or {})}
    for kind, value in wanted.items():
        if kind in have and abs(have[kind] - value) > max(0.01, 0.02 * value):
            return 0.0
        if kind not in have:
            # 125 g of berries is not a 200 ml drink.
            if {"g", "ml"} & {kind} and {"g", "ml"} & set(have):
                return 0.0
            score -= 0.1
    # Numbered sizes ("BABYDRY S6", "13-19 KG") and ranges must agree.
    for pattern in (r"\bs(?:tr(?:lk)?)?\s?(\d{1,2})\b", r"\b(\d{1,3}\s?-\s?\d{1,3})\b"):
        mine = re.search(pattern, receipt.casefold())
        theirs = re.findall(r"\b(\d{1,3}(?:\s?-\s?\d{1,3})?)\b", product.casefold())
        if mine and theirs and re.sub(r"\s", "", mine.group(1)) not in {re.sub(r"\s", "", t) for t in theirs}:
            return 0.0
    if "ekologisk" in words and not re.search(r"\beko|ekologisk|krav", fold(f"{product} {brand or ''}")):
        score -= 0.2
    # A product with many words the receipt does not name is a weaker match.
    own = set(_tokens(_SIZE.sub(" ", product)))  # the brand never counts against a product
    extra = [n for n in names if n in own and n not in _STOP and len(n) >= 4 and not any(n.startswith(w) or w.startswith(n) for w in words)]
    return max(0.0, score - 0.05 * len(extra))


def plan_items(response):
    """The bought rows of a plan's basket."""
    rows = []
    for store in ((response or {}).get("optimized_basket") or {}).get("stores") or []:
        for item in store.get("items") or []:
            rows.append({"key": f"{store.get('store_id')}|{item.get('product_id')}",
                         "product": item.get("product_name") or "", "ingredient": re.sub(r"\s*\[\d+\]$", "", item.get("ingredient") or ""),
                         "store_id": store.get("store_id"), "store_name": store.get("store_name") or "", "gtin": item.get("gtin")})
    return rows


def _chain_of(name):
    folded = fold(name)
    return next((chain for chain, pattern in CHAINS if re.search(pattern, folded)), None)


def find_store(store_text, chain, known_stores):
    """The Smako store the receipt is from: (store_id, name, known)."""
    words = set(_tokens(store_text)) - {"ica", "coop", "willys", "hemköp", "hemkop", "lidl", "city", "gross", "ab", "butik",
                                         "nära", "kvantum", "maxi", "supermarket", "stora"}
    # One store can have several price contexts (store prices, online prices):
    # all contexts with the best name count as that store.
    names = {}
    for s in known_stores:
        if not chain or _chain_of(s["name"]) == chain or (s.get("chain") or "").casefold() == chain:
            names.setdefault(s["name"], []).append(s["store_id"])
    scored = sorted(((len(words & set(_tokens(name))), name) for name in names), reverse=True)
    if scored and scored[0][0] >= 1 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return tuple(names[scored[0][1]]), scored[0][1], True
    return None, store_text, False


class StoreProducts:
    """Smako's products in one store, looked up by receipt line (word index)."""

    def __init__(self, products):
        self.products, self.index = list(products), {}
        for i, product in enumerate(self.products):
            for token in set(_tokens(f"{product.get('brand') or ''} {product['name']}")):
                if len(token) >= 3 and token not in _STOP:
                    # Word starts and ends: "BAK" finds Bakpotatis, "KETCHUP" Tomatketchup.
                    for key in {token[:3], "~" + token[-4:]}:
                        self.index.setdefault(key, []).append(i)

    def find(self, line):
        """(product, confidence); see _find. Among equally good products the one
        whose price is the paid price wins (same name in two sizes)."""
        return self._find(line)

    def _find(self, line):
        """(product, confidence): "exact" (barcode), "sure", "unsure" or None."""
        if line.get("gtin"):
            hit = next((p for p in self.products if p.get("gtin") == line["gtin"]), None)
            if hit:
                return hit, "exact"
        candidates = {i for w in _tokens(_SIZE.sub(" ", line["description"])) if len(w) >= 3 and w not in _STOP
                      for key in (w[:3], "~" + w[-4:]) for i in self.index.get(key, ())}
        scored = sorted(((_similarity(line["description"], self.products[i]["name"], self.products[i].get("sizes"),
                                      self.products[i].get("brand")), i)
                         for i in candidates), reverse=True)
        if not scored or scored[0][0] < 0.5:
            return None, None
        top = [i for score, i in scored if score >= scored[0][0] - 0.05]
        paid = _paid(line)
        priced = [i for i in top if (d := _price_differs(line, self.products[i])) is not None and not d[0]]
        if priced:
            return self.products[priced[0]], "sure" if scored[0][0] >= 0.75 else "unsure"
        best = self.products[top[0]]
        sure = scored[0][0] >= 0.75 and all(self.products[i]["name"] == best["name"] for i in top)
        if sure and len(top) > 1:
            # Same name in several sizes: compare with the closest price.
            best = min((self.products[i] for i in top), key=lambda p: min((abs(v - paid) for v in _prices(p)), default=1e9))
        return best, "sure" if sure else "unsure"


def _prices(product):
    """Every price Smako knows for one package: ordinary, campaign, member and
    club prices, and a multi-buy offer ("2 för 32") per package."""
    return [v for v in (product.get("price"), product.get("effective_price"), product.get("member_price"),
                        *product.get("offer_prices", ())) if v]


def _paid(line):
    """What one package cost: a quantity line after its discount ("2 st", "2 för 28")."""
    if line.get("quantity") and line.get("unit") == "st" and line["quantity"] >= 1:
        return round(line["price"] / line["quantity"], 2)
    return line["price"]


def offer_prices(offers):
    """Per-package prices of a product's offers (not per-kg offers)."""
    result = []
    for offer in offers or ():
        price = offer.get("price") if isinstance(offer, dict) else getattr(offer, "price", None)
        description = (offer.get("description") if isinstance(offer, dict) else getattr(offer, "description", "")) or ""
        basis = offer.get("price_basis_unit") if isinstance(offer, dict) else getattr(offer, "price_basis_unit", None)
        if not price or basis == "kg":
            continue
        many = re.search(r"(\d+)\s*för", description)
        result.append(round(price / int(many.group(1)), 2) if many and int(many.group(1)) > 1 else price)
    return result


def kg_prices(product):
    """Kilo prices of a product Smako has sold by weight (ordinary and kilo offers)."""
    sale = str(getattr(product, "sale_model", "") or "")
    if not sale.endswith(("sold_by_weight", "variable_weight_package")):
        return []
    prices = [product.comparison_price] if product.comparison_price and product.comparison_unit == "kg" else []
    prices += [o.price for o in product.offers or () if o.price and getattr(o, "price_basis_unit", None) == "kg"]
    return prices


def _price_differs(line, product):
    """Whether the paid price matches none of the product's known prices.

    Weighed goods ("0,485kg*43,95kr/kg") compare their kilo price with a
    product Smako has sold by weight; a packed bag is another product.
    """
    if line.get("unit") in {"kg", "g"}:
        prices, paid = product.get("kg_prices") or [], line.get("unit_price")
        if not prices or not paid:
            return None
    else:
        prices, paid = _prices(product), _paid(line)
    if not prices:
        return None
    closest = min(prices, key=lambda v: abs(v - paid))
    return abs(paid - closest) >= max(0.5, 0.01 * closest), round(closest, 2)


def evaluate(parsed, response, rules, known_stores, *, store_text=None, store_products=None):
    """Owner decision 2026-11-22 (second): any bought item counts, on the list or not.

    Each readable line of a receipt from a store without Smako prices, and each
    line Smako has no product for in a known store, gives receipt_missing_points;
    a line whose product Smako knows at another price gives receipt_price_points.
    The plan's shopping list is shown for reference only.
    """
    rows = plan_items(response)
    store_text = (store_text or parsed["store_text"])[:120]
    chain = _chain_of(store_text) or parsed.get("chain")
    store_id, store_name, known = find_store(store_text, chain, known_stores)
    catalogue = store_products(store_id) if known and store_products else None
    used, lines = set(), []
    for line in parsed["lines"][:80]:
        out = {**line, "item": None, "smako_product": None, "planned_price": None, "price_differs": False,
               "missing_in_smako": False, "unsure": False, "points": 0}
        best = None
        for row in rows:
            if row["key"] in used:
                continue
            s = 2.0 if line.get("gtin") and line.get("gtin") == row.get("gtin") else max(
                _similarity(line["description"], row["product"]), _similarity(line["description"], row["ingredient"]) * 0.9)
            if s >= 0.6 and (best is None or s > best[0]):
                best = (s, row)
        if best:
            used.add(best[1]["key"])
            out["item"] = best[1]["product"] or best[1]["ingredient"]
        if not known:
            out["missing_in_smako"] = True
        elif catalogue is not None:
            product, confidence = catalogue.find(line)
            if product is None:
                out["missing_in_smako"] = True
            elif confidence == "unsure":
                # Not sure which product it is: no points until the barcode says.
                out["smako_product"], out["unsure"] = product["name"], True
            else:
                out["smako_product"] = product["name"]
                compared = _price_differs(line, product)
                if compared and compared[0] and not 1 / 3 <= _paid(line) / compared[1] <= 3:
                    # 1,95 against 51,05: a single piece and a multipack, not another price.
                    out["unsure"] = True
                elif compared:
                    out["price_differs"], out["planned_price"] = compared
        out["points"] = (rules.receipt_missing_points if out["missing_in_smako"]
                         else rules.receipt_price_points if out["price_differs"] else 0)
        lines.append(out)
    qualifies = len(lines) >= rules.receipt_min_list_items
    points = min(rules.receipt_max_points, rules.receipt_points + sum(l["points"] for l in lines)) if qualifies else 0
    return {"store_text": store_text, "store": store_name if known else None, "store_known": known,
            "purchased_on": parsed.get("purchased_on"), "lines": lines, "matched": sum(1 for l in lines if l["item"]),
            "list_items": len(rows), "qualifies": qualifies, "points": points, "needed": rules.receipt_min_list_items,
            "max_points": rules.receipt_max_points}


def fingerprint(store_text, purchased_on, lines):
    body = json.dumps([fold(store_text)[:40], purchased_on, sorted((fold(l["description"])[:30], round(l["price"], 2)) for l in lines)],
                      ensure_ascii=False)
    return hashlib.sha256(body.encode()).hexdigest()


def load_plan(store, owner, plan_id):
    with store._connect() as db:
        row = db.execute("""SELECT owner_actor_hash, response_json FROM consumer_plan_revisions WHERE plan_id=?
                            ORDER BY revision DESC LIMIT 1""", (plan_id,)).fetchone()
    if not row or row["owner_actor_hash"] != owner:
        raise RewardError("Vi hittar inte planen. Öppna handlingslistan du handlade efter och försök igen.")
    return json.loads(row["response_json"])


def save_receipt(store, owner, plan_id, result, rules):
    """Keep the confirmed lines and give the points once per receipt."""
    if not result["qualifies"]:
        raise RewardError(f"Kvittot ger poäng när minst {result['needed']} varor går att läsa på det.")
    since = (datetime.now(UTC) - timedelta(days=7)).isoformat()
    key = fingerprint(result["store_text"], result["purchased_on"], result["lines"])
    receipt_id = secrets.token_hex(12)
    with store._connect() as db:
        db.execute("BEGIN IMMEDIATE")
        recent = db.execute("SELECT COUNT(*) FROM member_receipts WHERE owner=? AND created_at>?", (owner, since)).fetchone()[0]
        if recent >= rules.receipt_max_per_week:
            raise RewardError(f"Du kan få poäng för högst {rules.receipt_max_per_week} kvitton per vecka.")
        if db.execute("SELECT 1 FROM member_receipts WHERE fingerprint=?", (key,)).fetchone():
            raise RewardError("Det här kvittot har redan gett poäng.")
        lines = [{k: l.get(k) for k in ("description", "price", "quantity", "unit", "unit_price", "gtin", "item", "smako_product",
                                         "planned_price", "price_differs", "missing_in_smako", "points")} for l in result["lines"]]
        db.execute("INSERT INTO member_receipts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (receipt_id, owner, _now(), plan_id, result["store_text"], int(result["store_known"]),
                    result["purchased_on"], key, json.dumps(lines, ensure_ascii=False), result["points"]))
        differs = sum(l["price_differs"] for l in lines)
        missing = sum(l["missing_in_smako"] for l in lines)
        parts = ["Kvitto"] + ([f"{differs} andra priser"] if differs else []) + ([f"{missing} varor utanför Smako"] if missing else [])
        db.execute("INSERT INTO member_points (owner, created_at, points, reason, receipt_id) VALUES (?, ?, ?, ?, ?)",
                   (owner, _now(), result["points"], f"{', '.join(parts)} · {result['store_text'][:60]}", receipt_id))
    return {"receipt_id": receipt_id, "points": result["points"], **points_summary(store, owner)}


def points_summary(store, owner):
    with store._connect() as db:
        balance = db.execute("SELECT COALESCE(SUM(points), 0) FROM member_points WHERE owner=?", (owner,)).fetchone()[0]
        history = [dict(r) for r in db.execute("""SELECT created_at, points, reason FROM member_points WHERE owner=?
                                                  ORDER BY id DESC LIMIT 20""", (owner,))]
    return {"balance": balance, "history": history}


def recent_receipts(store, limit=50):
    """For the admin page: newest receipts without owner identities."""
    with store._connect() as db:
        rows = db.execute("""SELECT created_at, store_text, store_known, purchased_on, lines_json, points
                             FROM member_receipts ORDER BY created_at DESC LIMIT ?""", (limit,)).fetchall()
    return [{**{k: r[k] for k in ("created_at", "store_text", "purchased_on", "points")},
             "store_known": bool(r["store_known"]), "lines": json.loads(r["lines_json"])} for r in rows]
