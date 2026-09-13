"""Profile only retained-fact loading against read-only public source mounts."""

import cProfile
import io
import json
import pstats
import time
from pathlib import Path

from app.services.personal_source_facts import load_retained_facts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

prepared = PreparedPriceUniverseArtifact.model_validate_json(
    Path("/inputs/combined-prices.json").read_bytes()
).restore()
started = time.perf_counter()
first = load_retained_facts(prepared, database="/srv/app/var/grocery/grocery_data.sqlite")
print(json.dumps({"first": time.perf_counter() - started, "facts": len(first)}), flush=True)
profile = cProfile.Profile()
profile.enable()
second = load_retained_facts(prepared, database="/srv/app/var/grocery/grocery_data.sqlite")
profile.disable()
assert second is first
profile.dump_stats("/output/facts-warm.prof")
buffer = io.StringIO()
pstats.Stats(profile, stream=buffer).strip_dirs().sort_stats("cumulative").print_stats()
Path("/output/facts-warm.txt").write_text(buffer.getvalue(), encoding="utf8")
print("\n".join(buffer.getvalue().splitlines()[:40]), flush=True)
