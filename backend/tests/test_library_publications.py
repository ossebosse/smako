import pytest
from app.services import library_publications as subject
from app.services.meal_library_content import identity, load_entries, manifest_entries
from app.services.planner_context import content_digest


def recipe_value(name, value=1):
    base = load_entries(manifest_entries()['current'][:1])[0].model_copy(deep=True)
    return base.model_copy(update={'name': name, 'servings': value,
        'design': base.design.model_copy(update={'base_id': 'smako-synthetic-' + name.lower()})})


@pytest.mark.parametrize("change", [None, "changed", "revoked", "mutated"])
def test_cold_publication_chain_binds_exact_order_values_and_predecessors(monkeypatch, change):
    a, b, c, d = [recipe_value(name) for name in "ABCD"]
    entries = [{"file": f"{n}.json", "sha256": str(n) * 64} for n in range(3)]
    generations = {1: (a, b), 2: (a, b, c), 3: (a, b, c, d)}
    if change == "changed":
        generations[3] = (recipe_value("A", 2), b, c, d)
    elif change == "revoked":
        generations[3] = (b, c, d)
    monkeypatch.setattr(subject, "manifest_entries", lambda: {"current": entries})
    def current(generation):
        if change == 'mutated' and generation == 3:
            a.instructions.append('Changed inside the same object between generations')
        return generations[generation]
    monkeypatch.setattr(subject, "current_recipes", current)
    monkeypatch.setattr(subject, "reference_manifest", lambda: {"manifest": {
        "entries": entries[:1], "recipes": [[identity(r), content_digest(r)] for r in (a, b)]}})
    subject._publications.cache_clear()
    first = subject._publications("synthetic", 3)
    subject._publications.cache_clear()
    assert subject._publications("synthetic", 3) == first
    if change:
        assert first == ()
    else:
        assert [p["count"] for p in first] == [2, 3, 4]
        assert first[0]["predecessor"] is None
        assert [p["predecessor"] for p in first[1:]] == [p["sha256"] for p in first[:-1]]
    subject._publications.cache_clear()
