"""Owner decision 2026-11-27: a general popularity rank for every dish.

Each dish (``design.base_id``) has a score from 1 (polarising, e.g. liver) to
5 (a favourite most people like, e.g. spaghetti och köttfärssås), compared with
other dishes of the same meal type and diet. Variants and scaled siblings share
the score of their dish.

The rank is kept outside the recipe designs on purpose: recipes are
content-hashed and versioned, and changing a rank must not create a new recipe
version. ``data/recipe_popularity.json`` is the single source; a test requires
a score for every current dish, so a new recipe cannot be merged without one.

Planned use (not active yet): only dishes at or above a cut-off become planner
candidates, liked dishes always pass, a typed like with no dish above the
cut-off unlocks the dishes that name it, and the cut-off is lowered one step
when too few dishes remain to fill the week.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Final

POPULARITY_PATH: Final = Path(__file__).resolve().parents[1] / "data" / "recipe_popularity.json"
SCORES: Final = (1, 2, 3, 4, 5)
DEFAULT_CUTOFF: Final = 3


@lru_cache(maxsize=1)
def _table() -> dict[str, dict]:
    data = json.loads(POPULARITY_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Okänd version av receptpopularitet.")
    recipes = data["recipes"]
    for base_id, row in recipes.items():
        if row.get("score") not in SCORES or not str(row.get("reason", "")).strip():
            raise ValueError(f"Ogiltig popularitet för {base_id}.")
    return recipes


def popularity(base_id: str) -> int | None:
    """The dish's score 1–5, or None when the dish has not been rated."""
    row = _table().get(base_id)
    return None if row is None else row["score"]


def popularity_reason(base_id: str) -> str | None:
    row = _table().get(base_id)
    return None if row is None else row["reason"]


def rated_dishes() -> frozenset[str]:
    return frozenset(_table())


def reset_popularity_cache() -> None:
    _table.cache_clear()
