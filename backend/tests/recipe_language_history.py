"""Keep older qualification receipts tied to their exact issued recipe bytes."""
import json
from functools import lru_cache

from app.services.meal_library_content import ROOT, identity, load_entries, manifest_entries
from app.services.recipe_library import current_recipes


@lru_cache(maxsize=1)
def language_review():
    return json.loads((ROOT.parents[3] / "docs/reviews/recipe-language-20261102/library-transition.json").read_bytes())


@lru_cache(maxsize=1)
def language_successors():
    followup = json.loads((ROOT.parents[3] / "docs/reviews/recipe-language-followup-20261102/library-transition.json").read_bytes())
    # Later reviewed successors (ingredients Malmö no longer sells) keep the same chain.
    malmo = json.loads((ROOT.parents[3] / "docs/reviews/malmo-unavailable-20261107/recipe-review.json").read_bytes())
    # The dinner-name review (2026-11-20) only renames; steps and amounts stay identical.
    names = json.loads((ROOT.parents[3] / "docs/reviews/recipe-names-20261120/library-transition.json").read_bytes())
    return {r["previous_id"]: r for review in (language_review(), followup, malmo, names) for r in review["corrected"]}


def after_language_id(recipe_id):
    while recipe_id in language_successors():
        recipe_id = language_successors()[recipe_id]["runtime_id"]
    return recipe_id


@lru_cache(maxsize=1)
def _malmo_previous():
    review = json.loads((ROOT.parents[3] / "docs/reviews/malmo-unavailable-20261107/recipe-review.json").read_bytes())
    return {r["runtime_id"]: r["previous_id"] for r in review["corrected"]}


def before_name_id(recipe_id):
    """The version just before the dinner-name review (2026-11-20)."""
    return {v: k for k, v in _renamed().items()}.get(recipe_id, recipe_id)


def before_malmo_id(recipe_id):
    """The version just before an ingredient Malmö no longer sells was replaced."""
    recipe_id = before_name_id(recipe_id)
    return _malmo_previous().get(recipe_id, recipe_id)


def before_language_id(recipe_id):
    previous = {r["runtime_id"]: r["previous_id"] for r in language_successors().values()}
    while recipe_id in previous:
        recipe_id = previous[recipe_id]
    return recipe_id


def current_language_cohort(pack_prefix):
    before = current_recipes(len(language_review()["before_manifest"]["current"]))
    keys = {(r.design.base_id, r.design.variant_id) for r in before
            if r.design.content_source and r.design.content_source.pack_id.startswith(pack_prefix)}
    return [r for r in current_recipes() if (r.design.base_id, r.design.variant_id) in keys]


@lru_cache(maxsize=1)
def _issued():
    manifest = manifest_entries()
    return {identity(r): r for r in load_entries(manifest["current"] + manifest["history"])}


def assert_current_language_version(recipe_id, content_sha256):
    # The previous qualification still certifies exactly its original bytes.
    assert _issued()[recipe_id].design.content_sha256 == content_sha256
    active = {identity(r): r for r in current_recipes()}
    while recipe_id in language_successors():
        successor = language_successors()[recipe_id]
        assert successor["previous_content_sha256"] == content_sha256
        recipe_id, content_sha256 = successor["runtime_id"], successor["content_sha256"]
        assert _issued()[recipe_id].design.content_sha256 == content_sha256
    assert active[recipe_id].design.content_sha256 == content_sha256


@lru_cache(maxsize=1)
def _renamed():
    review = json.loads((ROOT.parents[3] / "docs/reviews/recipe-names-20261120/library-transition.json").read_bytes())
    return {r["previous_id"]: r["runtime_id"] for r in review["corrected"]}


def assert_same_apart_from_name(current, original):
    """A recipe untouched except by the dinner-name review (2026-11-20)."""
    rid = identity(original)
    if rid not in _renamed():
        assert current[rid].model_dump() == original.model_dump()
        return
    renamed = current[_renamed()[rid]].model_dump()
    before = original.model_dump()
    for dump in (renamed, before):
        dump.pop("name")
        for key in ("version", "content_sha256", "content_source", "review", "provenance"):
            dump["design"].pop(key, None)
        if dump.get("preparation"):
            dump["preparation"].pop("parent_sha256", None)
    assert renamed == before
