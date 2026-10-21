from types import SimpleNamespace


def test_full_library_reference_keeps_every_variant_of_a_family():
    """Review 2026-10-18 P2: --uncapped must not keep the four-per-base shortlist."""
    from app.services.meal_library_content import manifest_entries
    from app.services.personal_planner import PersonalPlanner
    from app.services.recipe_candidate_validator import recipe_id
    from app.services.recipe_library import current_recipes

    family = [r for r in current_recipes(len(manifest_entries()["current"]))
              if r.design.base_id == "smako-mexican-lentil-chili"]
    assert len(family) > 4
    from app.services.stable_candidate_pool import VariantSearchEvidence
    evidence = {("dinner", recipe_id(r)): VariantSearchEvidence(paid=10 + n, nutrients=(), packages=frozenset())
                for n, r in enumerate(family)}
    planner = SimpleNamespace(variant_search_evidence=evidence, _recipe_id=recipe_id)
    groups = [[SimpleNamespace(meal_type="dinner", recipe=r) for r in family]]

    def kept(**kwargs):
        (group,) = PersonalPlanner._select_library_options(planner, groups, **kwargs)
        return len(group)

    assert kept(limit=0, shortlist_variants=True) == 4  # default seed: shortlist active
    assert kept(limit=0, shortlist_variants=False) == len(family)  # full-library reference


def test_library_option_selection_keeps_empty_slot_groups():
    """A newer generation may add no recipe for a meal type (e.g. breakfast)."""
    from app.services.personal_planner import PersonalPlanner
    from app.services.recipe_candidate_validator import recipe_id

    planner = SimpleNamespace(variant_search_evidence={}, _recipe_id=recipe_id)
    assert PersonalPlanner._select_library_options(planner, [[], []], limit=40, shortlist_variants=False) == [[], []]
