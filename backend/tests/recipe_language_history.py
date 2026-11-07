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
    return {r["previous_id"]: r for review in (language_review(), followup, malmo) for r in review["corrected"]}


def after_language_id(recipe_id):
    while recipe_id in language_successors():
        recipe_id = language_successors()[recipe_id]["runtime_id"]
    return recipe_id


@lru_cache(maxsize=1)
def _malmo_previous():
    review = json.loads((ROOT.parents[3] / "docs/reviews/malmo-unavailable-20261107/recipe-review.json").read_bytes())
    return {r["runtime_id"]: r["previous_id"] for r in review["corrected"]}


def before_malmo_id(recipe_id):
    """The version just before an ingredient Malmö no longer sells was replaced."""
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
