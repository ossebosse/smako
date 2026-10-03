"""Test-only sampled diagnostic of one unchanged frozen ordinary plan request.

No locals, credentials, provider collection, product patches or search overrides.
Sampling changes execution overhead: this is NOT a clean performance benchmark.
Run only after the shared isolated replay resource has been handed over.
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import hashlib
import json
import os
import sys
import threading
import time
from collections import Counter
from pathlib import Path


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def validate_request(payload):
    from app.models import PlanRequest

    if set(payload) - set(PlanRequest.model_fields):
        raise ValueError("Request contains fields outside the ordinary plan contract")
    request = PlanRequest.model_validate(payload)
    if (request.diversity_mode != "varied" or request.recipes != 5 or request.servings != 2
            or request.max_stores != 2 or not request.recipe_preferences
            or request.recipe_preferences.mode != "complete" or request.recipe_preferences.cuisines
            or not request.personal or request.personal.pantry_revision != 0
            or request.personal.slots or request.personal.product_locks or request.personal.extras):
        raise ValueError("Expected original free unrestricted-varied request with empty revision-zero state")
    return request


def extract_request(report_path, destination):
    """Copy only the submitted request; omit HTTP/session/plan response evidence."""
    data = report_path.read_bytes()
    report = json.loads(data)
    result = report["result"]
    if report["case"] != "unrestricted-varied" or result["private_stock"] != "empty":
        raise ValueError("Only unrestricted-varied with an explicitly empty private workspace is supported")
    payload = result["request"]
    validate_request(payload)
    envelope = {
        "case": "unrestricted-varied", "private_state": "empty_revision_0",
        "request": payload, "request_sha256": _digest(payload),
        "source_report_sha256": hashlib.sha256(data).hexdigest(),
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Evidence files are immutable; a repeat needs a new destination.
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(envelope, stream, ensure_ascii=False, indent=2)
    return envelope


def frame_stack(frame, *, maximum_depth=256):
    """Read code location only: never f_locals, globals, source text or repr(frame)."""
    result = []
    while frame is not None and len(result) < maximum_depth:
        code = frame.f_code
        path = code.co_filename.replace("\\", "/")
        # Relative source locations avoid exporting host/user directory names.
        for marker in ("/backend/app/", "/grocery_data/app/", "/scripts/recipe_layer/"):
            if marker in path:
                path = marker[1:] + path.split(marker, 1)[1]
                break
        else:
            path = path.rsplit("/", 1)[-1]
        result.append((path, code.co_name, frame.f_lineno))
        frame = frame.f_back
    return tuple(reversed(result))


class StackSampler:
    """Best-effort Python thread stack samples, with bounded aggregate storage."""

    def __init__(self, *, interval_seconds=0.05, maximum_stacks=20000, select=None):
        if not 0.01 <= interval_seconds <= 1 or maximum_stacks < 1:
            raise ValueError("Invalid bounded sampling settings")
        self.interval_seconds = interval_seconds
        self.maximum_stacks = maximum_stacks
        self.select = select or (lambda stack: any(
            path.startswith(("backend/app/", "grocery_data/app/")) for path, _, _ in stack))
        self.stacks = Counter()
        self.sample_cycles = self.selected_thread_samples = self.ignored_thread_samples = 0
        self.overflow_samples = 0
        self.sampling_seconds = 0.0
        self.cadence = []
        self._stop = threading.Event()
        self._thread = None

    def capture(self):
        started = time.perf_counter()
        own_thread = threading.get_ident()
        # Frames are short-lived references; retain only filename/name/line tuples.
        frames = sys._current_frames()
        try:
            for thread_id, frame in frames.items():
                if thread_id == own_thread:
                    continue
                stack = frame_stack(frame)
                if not self.select(stack):
                    self.ignored_thread_samples += 1
                    continue
                self.selected_thread_samples += 1
                if stack in self.stacks or len(self.stacks) < self.maximum_stacks:
                    self.stacks[stack] += 1
                else:
                    self.overflow_samples += 1
            self.sample_cycles += 1
        finally:
            del frames
        self.sampling_seconds += time.perf_counter() - started

    def _run(self):
        previous = time.perf_counter()
        while not self._stop.wait(self.interval_seconds):
            current = time.perf_counter()
            if len(self.cadence) < 100000:
                self.cadence.append(current - previous)
            previous = current
            self.capture()

    def __enter__(self):
        self._thread = threading.Thread(target=self._run, name="test-stack-sampler", daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *_):
        self._stop.set()
        self._thread.join(timeout=2)
        if self._thread.is_alive():
            raise RuntimeError("Diagnostic sampler did not stop")

    def report(self):
        inclusive, leaf = Counter(), Counter()
        for stack, count in self.stacks.items():
            for function in {(path, name) for path, name, _ in stack}:
                inclusive[function] += count
            if stack:
                leaf[stack[-1]] += count
        cadence = sorted(self.cadence)
        return {
            "kind": "sampled_diagnostic_not_benchmark", "locals_collected": False,
            "scope": "all Python threads with an application/planner frame; sampler excluded",
            "interval_requested_seconds": self.interval_seconds,
            "interval_observed_median_seconds": cadence[len(cadence) // 2] if cadence else None,
            "interval_observed_max_seconds": max(cadence, default=None),
            "sample_cycles": self.sample_cycles, "selected_thread_samples": self.selected_thread_samples,
            "ignored_thread_samples": self.ignored_thread_samples,
            "sampling_capture_wall_seconds": self.sampling_seconds,
            "maximum_unique_stacks": self.maximum_stacks, "overflow_samples": self.overflow_samples,
            "interpretation": "Observed Python stack occupancy, not call counts or exact function duration. GIL scheduling and native calls can bias samples. Inclusive percentages overlap.",
            "inclusive_functions": [{"file": path, "function": name, "samples": count}
                for (path, name), count in inclusive.most_common()],
            "leaf_locations": [{"file": path, "function": name, "line": line, "samples": count}
                for (path, name, line), count in leaf.most_common()],
            "stacks": [{"samples": count, "frames": [
                {"file": path, "function": name, "line": line} for path, name, line in stack]}
                for stack, count in self.stacks.most_common()],
        }


async def sample_plan(request_file, destination, interval_seconds):
    # Match the isolated replay launcher. Source mounts must also be read-only
    # and the diagnostic container must have --network none. No source fetches.
    os.environ.update(PYTHON_DOTENV_DISABLED="1", GROCERY_DATABASE_URL="sqlite:////inputs/grocery.sqlite",
                      GROCERY_RAW_SNAPSHOT_ROOT="/inputs/raw")
    from app.config import Settings
    from app.services.meal_plan_optimizer import MealPlanService
    from app.services.performance_trace import activate_performance_trace
    from app.services.price_universe_runtime import PreparedPriceUniverseManager
    from replay import install_clock

    envelope = json.loads(request_file.read_bytes())
    if (envelope["case"] != "unrestricted-varied" or envelope["private_state"] != "empty_revision_0"
            or _digest(envelope["request"]) != envelope["request_sha256"]):
        raise ValueError("Request provenance mismatch")
    request = validate_request(envelope["request"])
    destination.mkdir(parents=True, exist_ok=False)
    clock = install_clock()
    freeze = json.loads(Path("/inputs/freeze.json").read_bytes())
    artifact = Path("/inputs/universe.json")
    if hashlib.sha256(artifact.read_bytes()).hexdigest() != freeze["artifact_sha256"]:
        raise ValueError("Frozen price artifact hash mismatch")
    manager = PreparedPriceUniverseManager()
    manager.load_file_and_activate(artifact)
    settings = Settings(price_provider="own", meal_plan_strategy="optimized", price_universe_required=True,
        complete_recipes_enabled=True, stable_candidate_search_enabled=True,
        allow_provider_fallback=False, allow_mock_fallback=False, openai_api_key=None)
    service = MealPlanService(settings, price_universe_manager=manager)
    summary = {"kind": "profiled diagnostic, not a clean benchmark", "request": envelope,
        "clock": clock.isoformat(), "artifact_sha256": freeze["artifact_sha256"],
        "stage": json.loads(Path("/evaluation/stage.json").read_bytes()),
        "facts": "ordinary retained-facts loader against the same read-only frozen source database/raw files",
        "state": "ordinary MealPlanService empty workspace, revision0; no account/session copied",
        "sampler_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (destination / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    sampler = StackSampler(interval_seconds=interval_seconds)
    started, cpu = time.perf_counter(), time.process_time()
    try:
        with sampler, activate_performance_trace() as trace:
            plan = await service.create_plan(request)
        (destination / "plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        summary.update(status="complete", total=plan.optimized_basket.total,
                       recipes=[r.name for r in plan.recipes], trace=dataclasses.asdict(trace.snapshot()))
    except BaseException as exc:
        summary.update(status="failed", error_type=type(exc).__name__,
                       code=getattr(exc, "code", None), failure_stage=getattr(exc, "stage", None))
        raise
    finally:
        summary.update(profiled_wall_seconds=time.perf_counter() - started,
                       profiled_process_cpu_seconds=time.process_time() - cpu)
        (destination / "stack-counts.json").write_text(json.dumps(sampler.report(), ensure_ascii=False, indent=2), encoding="utf-8")
        (destination / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({key: summary[key] for key in ("kind", "status", "profiled_wall_seconds")}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser("extract")
    extract.add_argument("report", type=Path)
    extract.add_argument("destination", type=Path)
    sample = commands.add_parser("sample")
    sample.add_argument("request", type=Path)
    sample.add_argument("destination", type=Path)
    sample.add_argument("--interval-ms", type=float, default=50)
    args = parser.parse_args()
    if args.command == "extract":
        result = extract_request(args.report, args.destination)
        print(json.dumps({key: result[key] for key in ("case", "request_sha256", "source_report_sha256")}))
    else:
        asyncio.run(sample_plan(args.request, args.destination, args.interval_ms / 1000))


if __name__ == "__main__":
    main()
