"""Isolated replay instrumentation, never imported by the production app."""
import json
import resource
import time
from pathlib import Path


def install(path):
    from app.services.plan_store import PlanStore
    from app.services.planner_admission import PlannerAdmissionController

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    def record(value):
        with destination.open('a') as stream:
            stream.write(json.dumps(value) + '\n')

    run = PlannerAdmissionController.run

    async def measured_run(self, key, factory):
        submitted = time.perf_counter()

        async def measured_factory():
            admitted, cpu = time.perf_counter(), time.process_time()
            try:
                return await factory()
            finally:
                record({'kind': 'new_calculation', 'queue_seconds': admitted - submitted,
                        'calculation_seconds': time.perf_counter() - admitted,
                        'cpu_seconds': time.process_time() - cpu,
                        'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss})

        return await run(self, key, measured_factory)

    PlannerAdmissionController.run = measured_run
    create = PlanStore.create

    def measured_create(self, *args, **kwargs):
        started = time.perf_counter()
        try:
            return create(self, *args, **kwargs)
        finally:
            record({'kind': 'save', 'wall_seconds': time.perf_counter() - started})

    PlanStore.create = measured_create
