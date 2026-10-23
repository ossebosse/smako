"""Pinned full recipe values and original per-package publication order."""
from functools import lru_cache
from pathlib import Path

from app.services.meal_library_content import identity, load_entries, read_json
from app.services.planner_context import content_digest

PIN = Path(__file__).parents[1] / "data/recipes/reference-library-262.json"


@lru_cache(maxsize=1)
def reference_manifest():
    envelope = read_json(PIN)
    value = envelope["manifest"]
    if envelope["sha256"] != content_digest(value):
        raise ValueError("Reference manifest hash mismatch")
    recipes = load_entries(value["entries"])
    # The manifest includes retired versions. The exact reviewed current values
    # and their order are pinned separately, not inferred from a sorted prefix.
    available = {identity(r): content_digest(r) for r in recipes}
    if len(value["recipes"]) != 262 or any(available.get(k) != digest for k, digest in value["recipes"]):
        raise ValueError("Reference recipe values differ from reviewed 262 library")
    return envelope


def reference_cohorts(options, current, *, first_generation):
    pin = reference_manifest()["manifest"]
    allowed = {identity(r): content_digest(r) for r in current}
    pinned = {key for key, digest in pin["recipes"] if allowed.get(key) == digest}
    generations = {}
    for index, entry in enumerate(pin["entries"], 1):
        for recipe in load_entries([entry]):
            generations.setdefault(identity(recipe), index)
    return [(generation, [[s for s in group if not s.recipe or not s.recipe.design
                            or (identity(s.recipe) in pinned
                                and generations[identity(s.recipe)] <= generation)]
                           for group in options])
            for generation in range(first_generation, len(pin["entries"]) + 1)]
