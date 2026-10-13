"""The municipal offer owner supersedes only its own legacy city target."""
import pytest

from grocery_data import __main__ as cli
from grocery_data.app.domain import Chain
from grocery_data.app.services.coop_offer_job import source_plan


@pytest.fixture
def configured(monkeypatch, tmp_path):
    def configure(code, city, *, enabled=True):
        monkeypatch.setenv("COOP_MUNICIPAL_OFFERS_ROOT", str(tmp_path))
        monkeypatch.setenv("COOP_MUNICIPAL_OFFERS_ENABLED", str(enabled).lower())
        monkeypatch.setenv("COOP_MUNICIPALITY_CODE", code)
        monkeypatch.setenv("COOP_MUNICIPAL_BUILD_CITY", city)
    return configure


@pytest.mark.parametrize("code,city", [("1281", "Lund"), ("1280", "Malmö"), ("1480", "Göteborg")])
def test_exact_municipal_offers_replace_legacy_without_broadening_online(configured, code, city):
    configured(code, city)
    other = "Malmö" if city == "Lund" else "Lund"
    targets, skipped = cli._collect_all_plan([city, other], selected_chains=frozenset({Chain.COOP}))
    assert (Chain.COOP, city, ("offers",)) not in targets
    assert (Chain.COOP, other, ("offers",)) in targets
    managed = [row for row in skipped if row.get("source_management") == "coop_municipal"]
    assert len(managed) == 1
    assert managed[0]["city"] == city and managed[0]["municipality_code"] == code
    assert managed[0]["roles"] == ("offers",) and managed[0]["status"] == "not_applicable"
    baskets = [row for row in targets if row[2] == ("basket",)]
    assert baskets == [(Chain.COOP, other if city == "Göteborg" else city, ("basket",))]
    if city == "Göteborg":
        assert any(row.get("city") == city and row.get("roles") == ("basket",)
                   and row["status"] == "skipped" for row in skipped)


def test_disabled_municipal_source_retains_legacy(configured):
    configured("1281", "Lund", enabled=False)
    targets, skipped = cli._collect_all_plan(["Lund"], selected_chains=frozenset({Chain.COOP}))
    assert (Chain.COOP, "Lund", ("offers",)) in targets
    assert not any(row.get("source_management") == "coop_municipal" for row in skipped)


def test_invalid_municipal_scope_does_not_suppress_legacy_or_hide_configuration_error(configured):
    configured("1280", "Lund")
    targets, skipped = cli._collect_all_plan(["Lund"], selected_chains=frozenset({Chain.COOP}))
    assert (Chain.COOP, "Lund", ("offers",)) in targets
    assert not any(row.get("source_management") == "coop_municipal" for row in skipped)
    assert source_plan()["status"] == "optional_configuration_error"
