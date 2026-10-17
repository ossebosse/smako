"""Load shared product facts once after startup, outside the planner queue.

The first complete-recipe plan otherwise loads and projects every retained
product fact inside the user's job (about 21 s in the 2026-10-16 beta sample).
Facts are user-independent and versioned by the active universe, so this runs
the exact same ``load_retained_facts`` call and fills its existing process
cache. It never takes the planner admission slot: a user who arrives meanwhile
is not queued behind it and, at worst, repeats the same deterministic load.
No price, scope, qualification or freshness rule is changed here.
"""

from __future__ import annotations

import threading
from time import perf_counter
from typing import Any


def warm_recipe_library(servings=(1, 2, 3, 4)) -> None:
    """Build the process caches every complete-recipe request validates against.

    After a restart the first plan otherwise prepares the whole current and
    historical library (about 20 s on one CPU for 176 dinners) inside the user's
    job. These are the same lru-cached functions the planner calls; nothing is
    recomputed differently and no user data is involved.
    """
    from app.services import recipe_library

    recipe_library._registered()
    recipe_library._registered_history()
    for count in servings:
        recipe_library._issued_index(count)
        recipe_library._registered_portions(count)


def schedule_source_facts_prewarm(settings, universes, *, loader=None, start=True,
                                  library_warmer=None) -> dict[str, Any]:
    report: dict[str, Any] = {"status": "not_run", "universes": [], "library": None}
    if not (settings.complete_recipes_enabled and settings.source_facts_prewarm_enabled):
        return report
    targets = list(universes)
    if not targets:
        return report
    if loader is None:
        from app.services.personal_source_facts import load_retained_facts as loader

    def run() -> None:
        report["status"] = "running"
        started = perf_counter()
        try:
            (library_warmer or warm_recipe_library)()
            report["library"] = {"status": "ready"}
        except Exception as exc:  # noqa: BLE001 - a failed warm-up must never affect serving.
            report["library"] = {"status": "failed", "error_type": type(exc).__name__}
        report["library"]["seconds"] = round(perf_counter() - started, 3)
        for prepared in targets:
            row = {"universe_id": prepared.universe.universe_id}
            started = perf_counter()
            try:
                facts = loader(prepared)
                row.update(status="ready", fact_rows=len(facts or {}))
            except Exception as exc:  # noqa: BLE001 - a failed warm-up must never affect serving.
                row.update(status="failed", error_type=type(exc).__name__)
            row["seconds"] = round(perf_counter() - started, 3)
            report["universes"].append(row)
        report["status"] = ("ready" if report["library"]["status"] == "ready"
                            and all(r["status"] == "ready" for r in report["universes"]) else "partial")

    report["status"] = "scheduled"
    if start:
        threading.Thread(target=run, name="source-facts-prewarm", daemon=True).start()
    else:
        run()
    return report
