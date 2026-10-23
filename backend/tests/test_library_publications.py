from types import SimpleNamespace

import pytest
from app.services import library_publications as subject
from app.services.meal_library_content import identity
from app.services.planner_context import content_digest


class RecipeValue:
    def __init__(self, name, value=1):
        self.name, self.value = name, value
        self.design = SimpleNamespace(base_id=name, version="1.0.0", variant_id="base")

    def model_dump(self, **kwargs):
        return {"name": self.name, "value": self.value}


@pytest.mark.parametrize("change", [None, "changed", "revoked"])
def test_cold_publication_chain_binds_exact_order_values_and_predecessors(monkeypatch, change):
    a, b, c, d = [RecipeValue(name) for name in "ABCD"]
    entries = [{"file": f"{n}.json", "sha256": str(n) * 64} for n in range(3)]
    generations = {1: (a, b), 2: (a, b, c), 3: (a, b, c, d)}
    if change == "changed":
        generations[3] = (RecipeValue("A", 2), b, c, d)
    elif change == "revoked":
        generations[3] = (b, c, d)
    monkeypatch.setattr(subject, "manifest_entries", lambda: {"current": entries})
    monkeypatch.setattr(subject, "current_recipes", lambda generation: generations[generation])
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
