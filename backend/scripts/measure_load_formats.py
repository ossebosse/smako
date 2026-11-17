"""How fast can an area's prepared price universe load? (server check)

Loads the active JSON artifact as the app does, then times a binary pickle of
the same restored objects: size, write and load. Nothing is written outside
/tmp. Usage inside the app image: ``python measure_load_formats.py malmö``.
"""
import gc
import json
import pickle
import sys
import time
from pathlib import Path

sys.path[:0] = ["/srv/app/backend", "/srv/app"]
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

root = Path("/srv/app/var/price_universes")
pointer = json.loads((root / "active" / f"city-{sys.argv[1]}.json").read_bytes())
path = root / pointer["artifact_file"]
started = time.perf_counter()
artifact = PreparedPriceUniverseArtifact.from_file(path)
parsed = time.perf_counter()
prepared = artifact.restore()
restored = time.perf_counter()
data = pickle.dumps(artifact, protocol=pickle.HIGHEST_PROTOCOL)
dumped = time.perf_counter()
del prepared, artifact
gc.collect()
gc.disable()  # loading allocates millions of objects; collections only slow it
loading = time.perf_counter()
again = pickle.loads(data).restore()
loaded = time.perf_counter()
gc.enable()
print(json.dumps({
    "json_mb": round(path.stat().st_size / 2**20), "json_parse_s": round(parsed - started, 1),
    "restore_s": round(restored - parsed, 1), "pickle_mb": round(len(data) / 2**20),
    "pickle_write_s": round(dumped - restored, 1), "pickle_load_s": round(loaded - loading, 1),
    "products": len(again.universe.products),
}), flush=True)
