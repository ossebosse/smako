"""Memory reclamation never invalidates live request-owned state."""
import gc
import weakref

import pytest
from app.services import planner_memory


class State:
    pass


@pytest.mark.parametrize("generation", [1, 2])
def test_unreachable_cycles_are_collected_and_live_state_is_retained(monkeypatch, generation):
    monkeypatch.setattr(planner_memory, "_allocator_trim", lambda: None)
    live = State()
    live.certificate = {"owner": "synthetic", "winner": ["same-exact-recipe"]}
    unused = State()
    unused.cycle = unused
    reference = weakref.ref(unused)
    previous = gc.isenabled()
    gc.disable()
    try:
        del unused
        assert reference() is not None
        report = planner_memory.release_idle_memory(generation=generation)
    finally:
        if previous:
            gc.enable()
    assert reference() is None
    assert live.certificate == {"owner": "synthetic", "winner": ["same-exact-recipe"]}
    assert report["allocator_supported"] is False
    assert report["allocator_released"] is None
    assert report["generation"] == generation
