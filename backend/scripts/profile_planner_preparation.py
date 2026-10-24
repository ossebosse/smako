"""Instrument the frozen acceptance runner without changing planner semantics.

Use SMAKO_PROFILE_ROOT for the source checkout, SMAKO_PROFILE_REPORT for the
JSON report, and the ordinary run_matrix.py CLI arguments. The recipe library
is mounted by the caller; its pinned reference stays in the source checkout.
Timings include instrumentation, and RSS deltas are observations, not allocated
bytes. Run uninstrumented matched samples separately for latency acceptance.
"""
from __future__ import annotations

import atexit
import json
import os
import runpy
import time
from collections import Counter
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

START = time.perf_counter()
ROOT = Path(os.environ.get("SMAKO_PROFILE_ROOT", "/review"))
REPORT = Path(os.environ["SMAKO_PROFILE_REPORT"])
STACK = []
ROWS = []
COUNTS = Counter()
UNIQUE = {}


def memory():
    result = {}
    status = Path("/proc/self/status")
    if status.exists():
        for line in status.read_text().splitlines():
            if line.startswith(("VmRSS:", "VmHWM:")):
                key, value, _ = line.split()
                result[key.rstrip(":")] = int(value) * 1024
    for name in ("current", "peak"):
        path = Path(f"/sys/fs/cgroup/memory.{name}")
        if path.exists():
            result[f"cgroup_{name}"] = int(path.read_text())
    return result


def save():
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    value = {"schema": "smako-preparation-profile-v1",
             "process_seconds": time.perf_counter() - START,
             "memory": memory(), "phases": ROWS, "counts": dict(COUNTS),
             "unique_baskets": {key: len(values) for key, values in UNIQUE.items()},
             "notes": ["Instrumented timings; use matched uninstrumented latency samples",
                       "Empty application cache does not imply cold OS disk"]}
    REPORT.write_text(json.dumps(value, indent=2), encoding="utf8")


atexit.register(save)


def instrument(owner, name, label=None):
    original = getattr(owner, name)

    @wraps(original)
    def measured(*args, **kwargs):
        phase = label or name
        start, cpu, before = time.perf_counter(), time.process_time(), memory()
        frame = {"name": phase, "child_seconds": 0.0}
        STACK.append(frame)
        try:
            return original(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            STACK.pop()
            if STACK:
                STACK[-1]["child_seconds"] += elapsed
            ROWS.append({"phase": phase, "seconds": elapsed,
                         "exclusive_seconds": elapsed - frame["child_seconds"],
                         "cpu_seconds": time.process_time() - cpu,
                         "before": before, "after": memory()})
            if phase.startswith("search") or phase == "create":
                save()

    setattr(owner, name, measured)


from app.services import library_publications, reference_library

reference_library.PIN = ROOT / "backend/app/data/recipes/reference-library-262.json"

from app.services.menu_optimizer import MenuOptimizer
from app.services.personal_planner import PersonalPlanner
from app.services.planner_artifacts import OwnedPlannerArtifacts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

try:
    from app.models import immutable_interning
except ImportError:
    pass  # The baseline revision predates artifact evidence interning.
else:
    original_pool = immutable_interning.immutable_model_pool

    @contextmanager
    def observed_pool():
        with original_pool() as pool:
            yield pool
            COUNTS["artifact_frozen_model_hits"] += pool.hits
            COUNTS["artifact_frozen_model_entries"] += pool.count
            COUNTS["artifact_pool_key_bytes"] += pool.retained_bytes

    immutable_interning.immutable_model_pool = observed_pool

for owner, name, label in (
    (PreparedPriceUniverseArtifact, "restore", "load_restore_indexes"),
    (library_publications, "publications", "publication_identity_hashing"),
    (PersonalPlanner, "__init__", "planner_init"),
    (PersonalPlanner, "_candidates", "qualification"),
    (PersonalPlanner, "_finalize_result", "finalize"),
    (PersonalPlanner, "create", "create"),
    (OwnedPlannerArtifacts, "load", "owned_artifact_load"),
    (OwnedPlannerArtifacts, "save", "owned_artifact_save"),
):
    instrument(owner, name, label)

SEARCH = MenuOptimizer.optimize_library_slots


@wraps(SEARCH)
def search(self, cohorts, **kwargs):
    cohorts = tuple(cohorts)
    label = "search:{}:{}".format(len(cohorts), cohorts[-1][0] if cohorts else "empty")
    instrumented = type("MeasuredSearch", (), {"run": staticmethod(SEARCH)})
    instrument(instrumented, "run", label)
    return instrumented.run(self, cohorts, **kwargs)


MenuOptimizer.optimize_library_slots = search
BASKET = PersonalPlanner.basket


@wraps(BASKET)
def basket(self, slots, *, final=True, **kwargs):
    phase = next((f["name"] for f in reversed(STACK) if f["name"].startswith("search")),
                 STACK[-1]["name"] if STACK else "other")
    key = f"{phase}:final={final}:deferred={getattr(self, '_defer_search_audit', False)}"
    COUNTS[key] += 1
    UNIQUE.setdefault(key, set()).add(tuple((s.id, id(s.recipe)) for s in slots))
    started = time.perf_counter()
    try:
        return BASKET(self, slots, final=final, **kwargs)
    finally:
        COUNTS[f"{key}:seconds"] += time.perf_counter() - started


PersonalPlanner.basket = basket
runpy.run_path(str(ROOT / "docs/reviews/integration-scaling-20261023/run_matrix.py"),
               run_name="__main__")
