"""Do threads slow each other down just by reading the same objects? (server check)

Free-threaded CPython updates the reference count of every object a thread
reads; for objects created by another thread that is an atomic operation on
shared memory. This reads the loaded product universe in 1 and N threads and
compares the time per pass with a pass over private copies, so we can tell
reference-count contention from lock contention in the planner.
Usage inside the app image: ``python measure_shared_reads.py malmö 6``.
"""
import copy
import json
import sys
import threading
import time
from pathlib import Path

sys.path[:0] = ["/srv/app/backend", "/srv/app"]
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

root = Path("/srv/app/var/price_universes")
city, count = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 6
pointer = json.loads((root / "active" / f"city-{city}.json").read_bytes())
prepared = PreparedPriceUniverseArtifact.from_file(root / pointer["artifact_file"]).restore()
shared = list(prepared.universe.products)[:20000]


def work(products):
    total = 0.0
    for _ in range(5):
        for product in products:
            total += (product.price or 0) + len(product.name) + len(product.offers)
    return total


def run(threads, private):
    lists = [copy.deepcopy(shared) if private else shared for _ in range(threads)]
    gate = threading.Barrier(threads)
    times = []

    def one(products):
        gate.wait()
        started = time.perf_counter()
        work(products)
        times.append(time.perf_counter() - started)

    pool = [threading.Thread(target=one, args=(products,)) for products in lists]
    for thread in pool:
        thread.start()
    for thread in pool:
        thread.join()
    return round(max(times), 2)


print(json.dumps({"gil": sys._is_gil_enabled() if hasattr(sys, "_is_gil_enabled") else True,
                  "one_thread": run(1, False),
                  f"{count}_threads_same_objects": run(count, False),
                  f"{count}_threads_own_copies": run(count, True)}), flush=True)
