"""Prepare shared recipe inputs after startup and price replacement.

The first complete-recipe plan otherwise loads and projects every retained
product fact inside the user's job (about 21 s in the 2026-10-16 beta sample).
Facts are user-independent and versioned by the active universe, so this runs
the exact same ``load_retained_facts`` call and fills its existing process
cache. It never takes the planner admission slot: a user who arrives meanwhile
is not queued behind it and, at worst, repeats the same deterministic load.
The existing versioned recipe preparation also covers standard servings 1–4;
it does not select meals or authorize purchases. Heavy warm-ups are serialized.
No price, scope, qualification or freshness rule is changed here.
"""

from __future__ import annotations

import threading
from time import perf_counter
from typing import Any

_PREPARATION_LOCK = threading.RLock()


def warm_recipe_library(servings=(1, 2, 3, 4), *, current_only=False) -> None:
    """Prepare exact issued values for the selected planning policy.

    Current-library planning does not need historical portion trees at startup.
    Saved older recipes still use validate_recipe_design's historical fallback
    on demand. Legacy/reference planning retains its full preparation.
    """
    from app.services import recipe_library

    recipe_library._registered()
    if not current_only:
        recipe_library._registered_history()
    for count in servings:
        if current_only:
            recipe_library._current_issued_index(count)
        else:
            recipe_library._issued_index(count)
        recipe_library._registered_portions(count)


def schedule_source_facts_prewarm(settings, universes, *, loader=None, start=True,
                                  library_warmer=None, preparer=None) -> dict[str, Any]:
    report: dict[str, Any] = {"status": "not_run", "universes": [], "library": None}
    if not (settings.complete_recipes_enabled and settings.source_facts_prewarm_enabled):
        return report
    targets = list(universes)
    if not targets:
        return report
    if loader is None:
        from app.services.personal_source_facts import load_retained_facts as loader
    prepare_sources = getattr(settings, "library_search_policy", "legacy") == "smako-current-library-v2"
    if prepare_sources and preparer is None:
        from app.services.meal_prepared_artifacts import prepare_current_sources as preparer

    def prepare() -> None:
        report["status"] = "running"
        started = perf_counter()
        try:
            if library_warmer is not None:
                library_warmer()
            else:
                warm_recipe_library(current_only=prepare_sources)
            report["library"] = {"status": "ready"}
        except Exception as exc:  # noqa: BLE001 - a failed warm-up must never affect serving.
            report["library"] = {"status": "failed", "error_type": type(exc).__name__}
        report["library"]["seconds"] = round(perf_counter() - started, 3)
        for prepared in targets:
            row = {"universe_id": prepared.universe.universe_id}
            started = perf_counter()
            try:
                facts = loader(prepared)
                if prepare_sources:
                    shared = preparer(prepared, facts if facts is not None else {}, portions=(1, 2, 3, 4))
                    if not shared["ready"] or shared["persistence_failures"]:
                        raise RuntimeError("Shared recipe preparation did not complete")
                    row["shared_preparation"] = {name: shared.get(name) for name in
                        ("ready", "content_variants", "portion_views", "persistence_failures")}
                row.update(status="ready", fact_rows=len(facts or {}))
            except Exception as exc:  # noqa: BLE001 - a failed warm-up must never affect serving.
                row.update(status="failed", error_type=type(exc).__name__)
            row["seconds"] = round(perf_counter() - started, 3)
            report["universes"].append(row)
        report["status"] = ("ready" if report["library"]["status"] == "ready"
                            and all(r["status"] == "ready" for r in report["universes"]) else "partial")

    def run() -> None:
        # Startup and municipal reloads share this worker boundary. No planner
        # admission slot or user profile is involved, and warm-ups cannot race
        # each other through the full current library.
        with _PREPARATION_LOCK:
            prepare()

    report["status"] = "scheduled"
    if start:
        threading.Thread(target=run, name="source-facts-prewarm", daemon=True).start()
    else:
        run()
    return report
