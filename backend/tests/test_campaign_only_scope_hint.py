from types import SimpleNamespace

from app.services.personal_planner import PersonalPlanner


def _store(store_id, name, coverage):
    return SimpleNamespace(store_id=store_id, name=name, coverage=coverage)


def _planner(stores, selected):
    return SimpleNamespace(view=SimpleNamespace(stores=stores), store_ids=set(selected))


STORES = [
    _store("ica-1", "ICA Nära Satelliten", "offers_only"),
    _store("lidl-1", "Lidl Magistratsvägen 6", "offers_only"),
    _store("willys-1", "Willys Lund", "full_catalog"),
    _store("coop-1", "Coop Online Syd", "full_online_catalog"),
]


def test_offers_only_scope_explains_and_suggests_complete_stores():
    hint = PersonalPlanner._campaign_only_scope_hint(_planner(STORES, {"ica-1", "lidl-1"}))

    assert "bara kampanjpriser" in hint
    assert "Coop Online Syd, Willys Lund" in hint


def test_scope_with_a_complete_catalogue_gets_no_hint():
    assert PersonalPlanner._campaign_only_scope_hint(_planner(STORES, {"ica-1", "willys-1"})) is None


def test_unknown_coverage_is_not_treated_as_offers_only():
    stores = [_store("x", "Okänd", None), *STORES]
    assert PersonalPlanner._campaign_only_scope_hint(_planner(stores, {"x", "ica-1"})) is None


def test_no_suggestion_when_the_area_has_no_complete_store():
    stores = STORES[:2]
    hint = PersonalPlanner._campaign_only_scope_hint(_planner(stores, {"ica-1"}))

    assert "bara kampanjpriser" in hint
    assert "fullt sortiment" not in hint
