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


@pytest.mark.asyncio
async def test_admission_cleanup_is_shared_once_across_worker_contexts_and_reset():
    import asyncio

    assert not planner_memory.consume_admission_cleanup()
    with planner_memory.admission_cleanup_scope():
        claimed = await asyncio.gather(*(asyncio.to_thread(
            planner_memory.consume_admission_cleanup) for _ in range(8)))
        assert claimed.count(True) == 1
        assert not planner_memory.consume_admission_cleanup()
    assert not planner_memory.consume_admission_cleanup()


def test_nested_or_failed_scope_does_not_consume_or_leak_another_jobs_credit():
    with planner_memory.admission_cleanup_scope():
        with pytest.raises(RuntimeError), planner_memory.admission_cleanup_scope():
            assert planner_memory.consume_admission_cleanup()
            raise RuntimeError("failed synthetic build")
        assert planner_memory.consume_admission_cleanup()
        assert not planner_memory.consume_admission_cleanup()
    assert not planner_memory.consume_admission_cleanup()
