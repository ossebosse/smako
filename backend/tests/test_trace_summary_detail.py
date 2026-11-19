import asyncio

from app.services import planning_diagnostics
from app.services.product_planning_trace import ProductPlanningTrace


def _trace():
    trace = ProductPlanningTrace.unrecorded()
    trace.products = {("s", "p"): {"product_id": "p", "contexts": {"a": 1}}}
    trace._pending_recipes = [(object(), "nutrition", "x"), (object(), None, None)]
    trace.search = {"r": {"recipe": {"id": "r"}, "events": {"kept": 1}}}
    return trace


def test_summary_skips_describing_recipes_and_product_contexts(monkeypatch):
    trace = _trace()
    monkeypatch.setattr(trace, "_describe_recipes", lambda: (_ for _ in ()).throw(AssertionError("described")))
    summary = trace.snapshot("summary")
    assert summary["detail"] == "summary"
    assert "recipe_needs" not in summary and "products" not in summary
    assert summary["followed_products"] == 1 and summary["evaluated_recipes"] == 2
    assert summary["recipes_by_stop"] == {"nutrition": 1, "passed": 1}
    assert summary["recipe_search"] == [{"recipe": {"id": "r"}, "events": {"kept": 1}}]


def test_full_detail_is_the_default():
    assert planning_diagnostics.DIAGNOSTIC_DETAIL.get() == "full"


def test_web_plans_run_with_the_summary(monkeypatch):
    from app.api import plan

    seen = []

    async def fake(work, warm=None):
        seen.append(planning_diagnostics.DIAGNOSTIC_DETAIL.get())
        return await asyncio.to_thread(lambda: planning_diagnostics.DIAGNOSTIC_DETAIL.get())

    monkeypatch.setattr(plan, "_run_personal_thread_in_context", fake)
    assert asyncio.run(plan._run_personal_thread(lambda: None)) == "summary"
    assert seen == ["summary"] and planning_diagnostics.DIAGNOSTIC_DETAIL.get() == "full"
