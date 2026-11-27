"""Tunable rules for meal planning, set on the admin page (owner request 2026-11-22).

"Allt som rör regler kring matplaneringen skulle vara bra att kunna göra
fine tuning på." The defaults are the owner's decisions so far; an admin can
change them under /admin, tab "Matplanering". The rules live next to the plan
store (``planning-rules.json``), so they survive releases, and apply to plans
made after a change. A missing or unreadable file means the defaults.
"""

from __future__ import annotations

import json
import math
import threading
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA = "smako-planning-rules-v1"
FILE_NAME = "planning-rules.json"
DINNER_COUNTS = 7  # tables hold 1–7 dinners; more dinners scale the last entry


def _table(default):
    return Field(default_factory=lambda: list(default), min_length=DINNER_COUNTS, max_length=DINNER_COUNTS)


class PlanningRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # "Allt": the least number of dinners of each kind, for 1–7 dinners.
    mixed_meat_min: list[int] = _table([1, 1, 1, 2, 2, 3, 3])
    mixed_fish_min: list[int] = _table([0, 0, 0, 1, 1, 1, 1])
    mixed_vegetarian_min: list[int] = _table([0, 1, 1, 1, 1, 1, 1])
    # "Fisk och vegetariskt": the least number of fish dinners.
    pescetarian_fish_min: list[int] = _table([1, 1, 1, 2, 2, 3, 3])
    # One kind of meat / one cuisine in at most this share of the dinners
    # (rounded up). 100 turns the rule off.
    meat_kind_max_percent: int = Field(default=50, ge=1, le=100)
    cuisine_max_percent: int = Field(default=50, ge=1, le=100)
    # Ranking weights, in kronor.
    extra_store_min_saving_kr: int = Field(default=10, ge=0, le=200)
    like_weight_kr: int = Field(default=15, ge=0, le=200)
    like_missing_kr: int = Field(default=1000, ge=0, le=100_000)
    # Owner decision 2026-11-24: a scaled recipe costs this much per grid step away
    # from the authored amounts, so the closest one that meets the limits wins.
    scaled_step_kr: int = Field(default=2, ge=0, le=200)
    # Owner decision 2026-11-27: dishes below this general popularity (1–5) are
    # proposed only when too few others fit; 1 turns the rule off.
    popularity_floor: int = Field(default=3, ge=1, le=5)
    # Variation of new plans.
    variation_percent: int = Field(default=10, ge=0, le=50)
    member_avoid_recent_plans: int = Field(default=2, ge=0, le=10)
    # Points for receipts (owner decision 2026-11-22, member_rewards.py).
    receipt_points: int = Field(default=10, ge=0, le=1000)
    receipt_price_points: int = Field(default=2, ge=0, le=1000)
    receipt_missing_points: int = Field(default=5, ge=0, le=1000)
    receipt_min_list_items: int = Field(default=3, ge=1, le=50)
    receipt_max_per_week: int = Field(default=5, ge=1, le=50)
    receipt_max_points: int = Field(default=100, ge=0, le=10_000)
    # Items learned from receipts (owner decisions 2026-11-24, member_rewards.py).
    receipt_item_temporary_days: int = Field(default=4, ge=1, le=60)
    receipt_item_persist_days: int = Field(default=7, ge=1, le=120)
    receipt_item_persist_points: int = Field(default=3, ge=0, le=1000)
    receipt_item_forget_days: int = Field(default=60, ge=7, le=730)

    @model_validator(mode="after")
    def _counts_fit(self):
        for n in range(1, DINNER_COUNTS + 1):
            for name in ("mixed_meat_min", "mixed_fish_min", "mixed_vegetarian_min", "pescetarian_fish_min"):
                value = getattr(self, name)[n - 1]
                if not 0 <= value <= n:
                    raise ValueError(f"{name}: {value} för {n} middagar ska vara mellan 0 och {n}")
            total = self.mixed_meat_min[n - 1] + self.mixed_fish_min[n - 1] + self.mixed_vegetarian_min[n - 1]
            if total > n:
                raise ValueError(f"Allt med {n} middagar kräver {total} rätter men har bara {n} platser")
        return self


DEFAULTS = PlanningRules()


def table_value(table, count: int) -> int:
    """The table's entry for ``count`` dinners; above 7, the 7-dinner share of ``count``."""
    if count < 1:
        return 0
    if count <= DINNER_COUNTS:
        return table[count - 1]
    return max(table[-1], math.floor(count * table[-1] / DINNER_COUNTS))


def share_cap(percent: int, count: int) -> int | None:
    """At most ``percent`` of ``count`` (rounded up); None when the rule is off."""
    if percent >= 100:
        return None
    return max(1, math.ceil(count * percent / 100))


def rules_path(settings) -> Path:
    return Path(settings.plan_store_path).resolve().parent / FILE_NAME


_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, PlanningRules]] = {}


def load(settings=None) -> PlanningRules:
    """The current rules, read again when the file changes."""
    if settings is None:
        from app.config import get_settings

        settings = get_settings()
    path = rules_path(settings)
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return DEFAULTS
    cached = _CACHE.get(str(path))
    if cached and cached[0] == mtime:
        return cached[1]
    try:
        data = json.loads(path.read_bytes())
        rules = PlanningRules.model_validate(data["rules"]) if data.get("schema") == SCHEMA else DEFAULTS
    except (OSError, ValueError, KeyError, TypeError):
        rules = DEFAULTS
    _CACHE[str(path)] = (mtime, rules)
    return rules


def save(settings, rules: PlanningRules) -> dict:
    from grocery_data.app.services.durable_files import atomic_write_bytes

    path = rules_path(settings)
    document = {"schema": SCHEMA, "updated_at": datetime.now(UTC).isoformat(), "rules": rules.model_dump()}
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(path, json.dumps(document, ensure_ascii=False, indent=1).encode())
        _CACHE.pop(str(path), None)
    return document


def document(settings) -> dict:
    path = rules_path(settings)
    updated = None
    try:
        data = json.loads(path.read_bytes())
        updated = data.get("updated_at")
    except (OSError, ValueError):
        pass
    return {"schema": SCHEMA, "updated_at": updated, "rules": load(settings).model_dump(),
            "defaults": DEFAULTS.model_dump()}
