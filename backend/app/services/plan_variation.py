"""Owner decision 2026-11-21: vary new plans a little.

1. A random preference among dinners. Each dinner gets a seeded random extra
   cost in the week comparison (never in what is paid) of at most
   VARIATION_PERCENT of a typical dinner's purchase. The search is unchanged and
   takes the same time; a different week is chosen only when it costs at most
   about VARIATION_PERCENT more than the week the search would otherwise find.
2. Members avoid the dinners of their most recent plans (a setting, counted in
   created plans). A new week and "Byt rätt" skip them; when no week fits, the
   oldest plans' dinners are allowed again first.
"""

from __future__ import annotations

import hashlib
import json
from statistics import median

from app.models.personal import VariationSettings

VARIATION_PERCENT = 10
SCAN_PLANS = 40


def variation_settings(state) -> VariationSettings:
    return VariationSettings.model_validate(state.get("variation") or {})


def jitter(seed: int, base_id: str) -> float:
    """A stable number in [0, 1) for one seed and dish."""
    digest = hashlib.sha256(f"{seed}:{base_id}".encode()).digest()
    return int.from_bytes(digest[:4], "big") / 2**32


# A dinner bought alone pays whole packages; in a week dinners share them. On
# beta (Lund, 2026-11-21) the cheap dinners' median lone purchase was 74 kr and
# their share of the chosen weeks 39-44 kr, so a dinner's share is about half.
WEEK_SHARE = 0.5


def per_dinner_kronor(paid_values) -> float:
    """The largest extra cost per dinner: VARIATION_PERCENT of a typical cheap dinner's week share."""
    paid = sorted(v for v in paid_values if v and v != float("inf"))[:10]
    return VARIATION_PERCENT / 100 * WEEK_SHARE * median(paid) if paid else 0.0


def recent_dinners(store, owner, plans: int) -> list[list[str]]:
    """Dinner base IDs of the owner's most recent created plans with dinners, newest first."""
    if plans <= 0:
        return []
    store._validate_owner_actor_hash(owner)
    with store._connect() as connection:
        ids = [row["plan_id"] for row in connection.execute(
            """SELECT plan_id, MIN(created_at) AS created FROM consumer_plan_revisions
               WHERE owner_actor_hash = ? GROUP BY plan_id ORDER BY created DESC LIMIT ?""",
            (owner, SCAN_PLANS))]
        result = []
        for plan_id in ids:
            row = connection.execute(
                """SELECT response_json FROM consumer_plan_revisions WHERE plan_id = ?
                   ORDER BY revision DESC LIMIT 1""", (plan_id,)).fetchone()
            slots = ((json.loads(row["response_json"]) or {}).get("personal") or {}).get("slots") or []
            bases = [((s.get("recipe") or {}).get("design") or {}).get("base_id") for s in slots
                     if s.get("meal_type") == "dinner"]
            bases = [b for b in bases if b]
            if bases:
                result.append(bases)
            if len(result) >= plans:
                break
    return result


def apply_variation(request, *, store, owner, state, member: bool):
    """Bind a new plan's seed and avoided dinners; existing values are kept."""
    personal = request.personal
    if personal is None or personal.slots is not None or not any(
            m.meal_type == "dinner" and m.count for m in personal.meals):
        return request
    settings = variation_settings(state)
    updates = {}
    if personal.variation_seed is None and settings.random_variation:
        # New for every created plan, but the same when the same request is sent
        # again before it is saved (a retry joins the running job).
        with store._connect() as connection:
            created = connection.execute(
                "SELECT COUNT(DISTINCT plan_id) FROM consumer_plan_revisions WHERE owner_actor_hash = ?",
                (owner,)).fetchone()[0]
        digest = hashlib.sha256(f"{owner}:{created}:{request.model_dump_json()}".encode()).digest()
        updates["variation_seed"] = int.from_bytes(digest[:4], "big")
    if member and not personal.avoid_recipes and settings.avoid_recent_plans:
        seen, ordered = set(), []
        for plan in recent_dinners(store, owner, settings.avoid_recent_plans):
            for base in plan:
                if base not in seen:
                    seen.add(base)
                    ordered.append(base)
        updates["avoid_recipes"] = ordered[:210]
    if not updates:
        return request
    return request.model_copy(update={"personal": personal.model_copy(update=updates)})
