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
picture. Points (planning_rules, admin tab "Matplanering"):
  * receipt_points for a receipt with at least receipt_min_list_items lines
    that match the plan's shopping list,
  * receipt_price_points per matched line whose price differs from the
    price Smako planned at that store,
  * receipt_missing_points per matched line bought where Smako has no
    prices (a store missing from Smako's price data).
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
_SKIP = re.compile(r"\b(?:total|totalt|summa|att betala|moms|netto|brutto|kort|kontant|växel|betal|bank|visa|"
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
    for line in raw:
        folded = fold(line)
        if re.match(r"^(?:totalt?|summa|att betala)\b", folded):
            ended = True
        if ended:
            continue
        price = _PRICE.search(line)
        if not price:
            # "2 st x 12,90" on its own line belongs to the line above.
            continue
        value = _number(price.group(1))
        description = line[:price.start()].strip(" .:*-\t")
        quantity = _QTY.search(line)
        if _SKIP.search(line) or not re.search(r"[A-Za-zÅÄÖåäö]{2}", description) and not quantity:
            continue
        if (value < 0 or _DISCOUNT.search(description)) and lines:
            lines[-1]["price"] = round(lines[-1]["price"] - abs(value), 2)
            lines[-1]["discount"] = True
            continue
        if value <= 0 or value > 5000:
            continue
        if quantity and lines and not re.search(r"[A-Za-zÅÄÖåäö]{3}", _QTY.sub("", description)):
            # A quantity line under its product: "0,532 kg x 29,90".
            lines[-1].update(quantity=_number(quantity.group(1)), unit=quantity.group(2).lower(),
                             unit_price=_number(quantity.group(3)), price=value)
            continue
        row = {"description": _QTY.sub("", description).strip()[:120] or description[:120], "price": value}
        if quantity:
            row.update(quantity=_number(quantity.group(1)), unit=quantity.group(2).lower(),
                       unit_price=_number(quantity.group(3)))
        lines.append(row)
    lines = [l for l in lines if l["price"] > 0][:80]
    if not lines:
        raise RewardError("Vi kunde inte läsa några varor på kvittot. Fota hela kvittot rakt uppifrån.")
    return {"store_text": store_text, "chain": chain, "purchased_on": purchased_on.isoformat() if purchased_on else None,
            "lines": lines, "header": header[:200]}


def _tokens(text):
    return [t for t in fold(re.sub(r"\[\d+\]", " ", text)).split() if len(t) >= 2 and not t.isdigit()]


def _similarity(receipt, product):
    """Share of the receipt line's words found as a word start in the product name."""
    words, names = _tokens(receipt), _tokens(product)
    if not words or not names:
        return 0.0
    hits = sum(any(n.startswith(w) or (len(w) >= 4 and w.startswith(n[:4]) and len(n) >= 4) for n in names) for w in words)
    if not any(len(w) >= 3 and any(n.startswith(w) for n in names) for w in words):
        return 0.0
    return hits / len(words)


def plan_items(response):
    """The bought rows of a plan's basket."""
    rows = []
    for store in ((response or {}).get("optimized_basket") or {}).get("stores") or []:
        for item in store.get("items") or []:
            rows.append({"key": f"{store.get('store_id')}|{item.get('product_id')}",
                         "product": item.get("product_name") or "", "ingredient": re.sub(r"\s*\[\d+\]$", "", item.get("ingredient") or ""),
                         "store_id": store.get("store_id"), "store_name": store.get("store_name") or "",
                         "chain": (item.get("chain") or "").casefold(), "gtin": item.get("gtin"),
                         "unit_price": item.get("unit_price"), "packages": item.get("packages_needed") or 1,
                         "total_price": item.get("total_price"), "comparison_price": item.get("comparison_price"),
                         "comparison_unit": item.get("comparison_unit"), "sale_model": item.get("sale_model")})
    return rows


def _chain_of(name):
    folded = fold(name)
    return next((chain for chain, pattern in CHAINS if re.search(pattern, folded)), None)


def find_store(store_text, chain, plan_rows, known_stores):
    """The plan store or Smako store the receipt is from: (store_id, name, known)."""
    words = set(_tokens(store_text)) - {"ica", "coop", "willys", "hemköp", "hemkop", "lidl", "city", "gross", "ab", "butik"}
    def score(name):
        names = set(_tokens(name))
        return len(words & names) + (1 if chain and _chain_of(name) == chain else 0)
    plan_stores = {(r["store_id"], r["store_name"]) for r in plan_rows}
    candidates = sorted(((score(n), sid, n) for sid, n in plan_stores), reverse=True)
    if candidates and candidates[0][0] >= 1 and (not chain or _chain_of(candidates[0][2]) == chain):
        # One plan store of the chain, or the one whose name the receipt names.
        same_chain = [c for c in candidates if not chain or _chain_of(c[2]) == chain]
        if len(same_chain) == 1 or candidates[0][0] >= 2:
            return candidates[0][1], candidates[0][2], True
    others = sorted(((score(s["name"]), s["store_id"], s["name"]) for s in known_stores
                     if not chain or _chain_of(s["name"]) == chain or s.get("chain", "").casefold() == chain), reverse=True)
    if others and others[0][0] >= 2:
        return others[0][1], others[0][2], True
    return None, store_text, False


def _differs(line, row):
    paid, planned = line["price"], row.get("total_price")
    if line.get("unit") == "kg" and line.get("unit_price") and row.get("comparison_unit") == "kg" and row.get("comparison_price"):
        paid, planned = line["unit_price"], row["comparison_price"]
    elif line.get("quantity") and line.get("unit") == "st" and line.get("unit_price") and row.get("unit_price"):
        paid, planned = line["unit_price"], row["unit_price"]
    elif row.get("unit_price") and row.get("packages", 1) > 1 and abs(paid - row["unit_price"]) < abs(paid - (planned or 0)):
        planned = row["unit_price"]
    if planned is None:
        return None
    return abs(paid - planned) >= max(1.0, 0.03 * planned), round(planned, 2)


def evaluate(parsed, response, rules, known_stores, *, store_text=None):
    """Matched lines and the points the receipt gives."""
    rows = plan_items(response)
    store_text = (store_text or parsed["store_text"])[:120]
    chain = _chain_of(store_text) or parsed.get("chain")
    store_id, store_name, known = find_store(store_text, chain, rows, known_stores)
    used, lines = set(), []
    for line in parsed["lines"][:80]:
        best = None
        for row in rows:
            if row["key"] in used:
                continue
            if line.get("gtin") and row.get("gtin") and line["gtin"] == row["gtin"]:
                best = (2.0, row)
                break
            s = max(_similarity(line["description"], row["product"]), _similarity(line["description"], row["ingredient"]) * 0.9)
            if s >= 0.5 and (best is None or s > best[0]):
                best = (s, row)
        out = {**line, "item": None, "planned_price": None, "price_differs": False, "missing_in_smako": False, "points": 0}
        if best:
            row = best[1]
            used.add(row["key"])
            out["item"] = row["product"] or row["ingredient"]
            if not known:
                out["missing_in_smako"] = True
                out["points"] = rules.receipt_missing_points
            elif row["store_id"] == store_id:
                compared = _differs(line, row)
                if compared:
                    out["price_differs"], out["planned_price"] = compared
                    out["points"] = rules.receipt_price_points if out["price_differs"] else 0
        lines.append(out)
    matched = sum(1 for l in lines if l["item"])
    qualifies = matched >= rules.receipt_min_list_items
    points = (rules.receipt_points + sum(l["points"] for l in lines)) if qualifies else 0
    return {"store_text": store_text, "store": store_name if known else None, "store_known": known,
            "purchased_on": parsed.get("purchased_on"), "lines": lines, "matched": matched,
            "list_items": len(rows), "qualifies": qualifies, "points": points,
            "needed": rules.receipt_min_list_items}


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
        raise RewardError(f"Kvittot ger poäng när minst {result['needed']} varor från handlingslistan finns på det.")
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
        lines = [{k: l.get(k) for k in ("description", "price", "quantity", "unit", "unit_price", "gtin", "item",
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
