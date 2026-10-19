"""On-demand pairwise culinary scores equal the former eager all-pairs dict."""
import pytest

from app.services.culinary_similarity import CulinarySimilarity
from app.services.menu_optimizer import DiversityConstraints, LazyPairwiseSimilarities
from app.services.recipe_library import current_recipes


def eager(profiles, compare):
    # The loop _culinary_constraints used before the lazy mapping.
    pairwise = {}
    rows = list(profiles.items())
    for index, (left_name, left_profile) in enumerate(rows):
        for right_name, right_profile in rows[index + 1:]:
            pairwise[tuple(sorted((left_name, right_name)))] = compare(left_profile, right_profile)
    return pairwise


@pytest.fixture(scope="module")
def library_profiles():
    similarity = CulinarySimilarity()
    recipes = [r for r in current_recipes() if "dinner" in r.design.meal_types][:70]
    profiles = {r.name.casefold().strip(): similarity.build_profile(r) for r in recipes}
    return profiles, (lambda left, right: similarity.compare_profiles(left, right).score)


def test_lazy_scores_keys_and_order_equal_the_eager_dict(library_profiles):
    profiles, compare = library_profiles
    expected = eager(profiles, compare)
    lazy = LazyPairwiseSimilarities(profiles, compare)
    assert lazy.calculated == 0
    assert len(lazy) == len(expected)
    assert list(lazy) == list(expected)
    for key, value in expected.items():
        assert key in lazy
        assert lazy.get(key) == value  # exact float equality, same argument order
    assert lazy.calculated == len(expected)


def test_lazy_lookup_of_unknown_or_unsorted_pairs_matches_dict_get(library_profiles):
    profiles, compare = library_profiles
    lazy = LazyPairwiseSimilarities(profiles, compare)
    name = next(iter(profiles))
    other = list(profiles)[1]
    reverse = tuple(sorted((name, other), reverse=True))
    for key in [(name, name), ("ingen sådan rätt", name), reverse, (name,), "x"]:
        assert key not in lazy
        assert lazy.get(key) is None
    assert lazy.calculated == 0


def test_only_looked_up_pairs_are_calculated_and_constraints_do_not_force_all():
    calls = []
    profiles = {"a": 1, "b": 2, "c": 3}

    def compare(left, right):
        calls.append((left, right))
        return 0.5

    lazy = LazyPairwiseSimilarities(profiles, compare)
    DiversityConstraints(pairwise_recipe_similarities=lazy)
    assert calls == []
    assert lazy[("a", "c")] == 0.5 and lazy[("a", "c")] == 0.5
    assert calls == [(1, 3)]  # earlier profile first, once


def test_out_of_range_score_is_rejected_when_calculated():
    lazy = LazyPairwiseSimilarities({"a": 1, "b": 2}, lambda left, right: 1.5)
    with pytest.raises(ValueError, match="between zero and one"):
        lazy.get(("a", "b"))
    with pytest.raises(ValueError, match="between zero and one"):
        DiversityConstraints(pairwise_recipe_similarities={("a", "b"): 1.5})
