import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from grocery_data import __main__ as cli
from grocery_data.app.connectors import SOURCE_COVERAGE, ConnectorDescriptor, ConnectorRegistry
from grocery_data.app.connectors.base import (
    SourcePolicyError,
    collection_policy_audit,
    enforce_collection_policy,
)
from grocery_data.app.connectors.citygross import CityGrossConnector
from grocery_data.app.connectors.citygross.client import CityGrossSourcePolicyError
from grocery_data.app.connectors.coop import CoopConnector, CoopOnlineCatalogConnector
from grocery_data.app.connectors.coop.online_catalog_client import (
    CoopOnlineSourcePolicyError,
)
from grocery_data.app.connectors.hemkop import HemkopConnector
from grocery_data.app.connectors.hemkop.client import HemkopSourcePolicyError
from grocery_data.app.connectors.lidl import LidlConnector
from grocery_data.app.connectors.willys import WillysConnector
from grocery_data.app.domain import Chain, CoverageLevel, SourceCollectionAudit, SourcePolicy


def test_registry_is_explicit_about_implemented_connectors() -> None:
    registry = ConnectorRegistry()
    connector = registry.create(Chain.WILLYS)
    assert isinstance(connector, WillysConnector)
    assert SOURCE_COVERAGE[Chain.LIDL].source_coverage == CoverageLevel.OFFERS_ONLY
    assert SOURCE_COVERAGE[Chain.LIDL].implemented is True
    assert SOURCE_COVERAGE[Chain.LIDL].acceptance_contract_passed is True
    ica = SOURCE_COVERAGE[Chain.ICA]
    assert ica.source_coverage == CoverageLevel.OFFERS_ONLY
    assert ica.acceptance_contract_passed is True
    assert "CAPTCHA" in (ica.limitation or "")
    coop = SOURCE_COVERAGE[Chain.COOP]
    assert coop.source_coverage is CoverageLevel.FULL_ONLINE_CATALOG
    assert coop.implemented is True
    assert coop.acceptance_contract_passed is True
    assert coop.missing_acceptance_checks == ()
    assert "730400" in (coop.limitation or "")
    assert "REVIEW" in (coop.limitation or "")
    citygross = SOURCE_COVERAGE[Chain.CITY_GROSS]
    assert citygross.source_coverage is CoverageLevel.FULL_ONLINE_CATALOG
    assert citygross.implemented is True
    assert citygross.acceptance_contract_passed is True
    assert "REVIEW" in (citygross.limitation or "")
    assert "Lund" in (citygross.limitation or "")
    hemkop = SOURCE_COVERAGE[Chain.HEMKOP]
    assert hemkop.source_coverage is CoverageLevel.FULL_ONLINE_CATALOG
    assert hemkop.implemented is True
    assert hemkop.acceptance_contract_passed is True
    assert "REVIEW" in (hemkop.limitation or "")
    assert "4247" in (hemkop.limitation or "")


def test_registry_factories_are_bounded_and_implemented() -> None:
    assert isinstance(ConnectorRegistry().create(Chain.COOP), CoopConnector)
    lidl = ConnectorRegistry().create(Chain.LIDL)
    assert isinstance(lidl, LidlConnector)
    assert lidl.coverage is CoverageLevel.OFFERS_ONLY
    assert lidl.client.max_pages == 1
    assert lidl.client.page_size == 5
    hemkop = ConnectorRegistry().create(Chain.HEMKOP)
    assert isinstance(hemkop, HemkopConnector)
    assert hemkop.coverage is CoverageLevel.PARTIAL_CATALOG
    assert hemkop.client.max_categories == 1
    assert hemkop.client.max_pages_per_category == 1
    assert hemkop.client.allow_full_crawl is False
    citygross = ConnectorRegistry().create(Chain.CITY_GROSS)
    assert isinstance(citygross, CityGrossConnector)
    assert citygross.coverage is CoverageLevel.PARTIAL_CATALOG
    assert citygross.client.max_pages == 1
    assert citygross.client.allow_full_crawl is False


def test_descriptor_cannot_claim_implemented_before_acceptance() -> None:
    with pytest.raises(ValidationError, match="must pass its coverage acceptance contract"):
        ConnectorDescriptor(
            chain=Chain.COOP,
            source_coverage=CoverageLevel.OFFERS_ONLY,
            implemented=True,
            acceptance_contract_passed=False,
            missing_acceptance_checks=("offers_fetch",),
        )


def test_citygross_operation_factories_keep_review_gate_atomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CITYGROSS_ALLOW_FULL_CRAWL", raising=False)
    monkeypatch.delenv("CITYGROSS_STORE_EXTERNAL_IDS", raising=False)

    discovery = cli._store_discovery_connector(Chain.CITY_GROSS)
    assert isinstance(discovery, CityGrossConnector)
    assert discovery.coverage is CoverageLevel.PARTIAL_CATALOG
    assert discovery.client.max_pages == 1
    assert discovery.client.allow_full_crawl is False
    bounded_audit = collection_policy_audit(discovery)
    assert bounded_audit is not None
    assert bounded_audit.model_dump(mode="json") == {
        "source_policy": "review",
        "operator_opt_in": False,
        "store_allowlist": [],
        "requests_per_second": 1.0,
        "max_concurrency": 1,
    }
    assert cli._policy_audit_fields(bounded_audit) == bounded_audit.model_dump(mode="json")

    with pytest.raises(CityGrossSourcePolicyError, match="explicitly"):
        cli._collection_connector(Chain.CITY_GROSS)

    monkeypatch.setenv("CITYGROSS_ALLOW_FULL_CRAWL", "true")
    monkeypatch.setenv("CITYGROSS_STORE_EXTERNAL_IDS", "3211")
    still_bounded = ConnectorRegistry().create(Chain.CITY_GROSS)
    assert still_bounded.coverage is CoverageLevel.PARTIAL_CATALOG
    assert still_bounded.client.max_pages == 1
    assert still_bounded.client.allow_full_crawl is False

    full = cli._collection_connector(Chain.CITY_GROSS)
    assert isinstance(full, CityGrossConnector)
    assert full.coverage is CoverageLevel.FULL_ONLINE_CATALOG
    assert full.client.max_pages is None
    assert full.client.allowed_store_ids == frozenset({"3211"})


def test_hemkop_operation_factories_keep_review_gate_atomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HEMKOP_ALLOW_FULL_CRAWL", raising=False)
    monkeypatch.delenv("HEMKOP_STORE_EXTERNAL_IDS", raising=False)

    discovery = cli._store_discovery_connector(Chain.HEMKOP)
    assert isinstance(discovery, HemkopConnector)
    assert discovery.coverage is CoverageLevel.PARTIAL_CATALOG
    assert discovery.client.max_categories == 1
    assert discovery.client.max_pages_per_category == 1
    assert discovery.client.allow_full_crawl is False
    bounded_audit = collection_policy_audit(discovery)
    assert bounded_audit is not None
    assert bounded_audit.operator_opt_in is False
    assert bounded_audit.store_allowlist == ()

    with pytest.raises(HemkopSourcePolicyError, match="explicitly"):
        cli._collection_connector(Chain.HEMKOP)

    monkeypatch.setenv("HEMKOP_ALLOW_FULL_CRAWL", "true")
    monkeypatch.setenv("HEMKOP_STORE_EXTERNAL_IDS", "4247")
    still_bounded = ConnectorRegistry().create(Chain.HEMKOP)
    assert still_bounded.coverage is CoverageLevel.PARTIAL_CATALOG
    assert still_bounded.client.max_categories == 1
    assert still_bounded.client.max_pages_per_category == 1
    assert still_bounded.client.allow_full_crawl is False
    assert still_bounded.client.allowed_store_ids == frozenset()
    assert still_bounded.client.store_allowed("4224") is True
    assert still_bounded.client.store_allowed("4247") is True

    full = cli._collection_connector(Chain.HEMKOP)
    assert isinstance(full, HemkopConnector)
    assert full.coverage is CoverageLevel.FULL_ONLINE_CATALOG
    assert full.client.max_categories is None
    assert full.client.max_pages_per_category is None
    assert full.client.allowed_store_ids == frozenset({"4247"})

    replay = cli._replay_connector(
        Chain.HEMKOP,
        coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        catalog_completion={"4247": {"complete": True}},
    )
    assert isinstance(replay, HemkopConnector)
    assert replay.coverage is CoverageLevel.FULL_ONLINE_CATALOG
    assert replay.client.allow_full_crawl is False
    assert replay.client.max_categories == 1
    assert replay.client.max_pages_per_category == 1
    assert replay.client.allowed_store_ids == frozenset({"4247"})

    canary = cli._canary_connector(Chain.HEMKOP)
    assert isinstance(canary, HemkopConnector)
    assert canary.coverage is CoverageLevel.PARTIAL_CATALOG
    assert canary.client.page_size == 5
    assert canary.client.max_categories == 1
    assert canary.client.max_pages_per_category == 1
    assert canary.client.allow_full_crawl is False
    assert canary.client.allowed_store_ids == frozenset()
    assert canary.client.store_allowed("4224") is True


def test_coop_exact_online_collection_and_replay_factories_are_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("COOP_ALLOW_FULL_CRAWL", raising=False)
    monkeypatch.delenv("COOP_ONLINE_CONTEXT_IDS", raising=False)

    # The ordinary registry remains the bounded physical-offers connector.
    # Naming an online context on the collect command does not itself grant
    # REVIEW authority.
    assert isinstance(ConnectorRegistry().create(Chain.COOP), CoopConnector)
    with pytest.raises(CoopOnlineSourcePolicyError, match="COOP_ALLOW_FULL_CRAWL"):
        cli._exact_collection_connector(Chain.COOP, "730400")

    monkeypatch.setenv("COOP_ALLOW_FULL_CRAWL", "true")
    monkeypatch.setenv("COOP_ONLINE_CONTEXT_IDS", "730400")
    with pytest.raises(CoopOnlineSourcePolicyError, match="outside COOP_ONLINE_CONTEXT_IDS"):
        cli._exact_collection_connector(Chain.COOP, "256600")

    full = cli._exact_collection_connector(Chain.COOP, "730400")
    assert full.coverage is CoverageLevel.FULL_ONLINE_CATALOG
    assert full.client.allow_full_crawl is True
    assert full.client.max_categories is None
    assert full.client.max_pages_per_category is None
    assert full.client.allowed_context_ids == frozenset({"730400"})
    full_audit = collection_policy_audit(full)
    assert full_audit is not None
    assert full_audit.operator_opt_in is True
    assert full_audit.store_allowlist == ("730400",)

    # Replay derives its exact context namespace only from immutable snapshot
    # completion evidence. It deliberately has no live full-crawl authority.
    replay = cli._replay_connector(
        Chain.COOP,
        coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        catalog_completion={"730400": {"complete": True}},
    )
    assert isinstance(replay, CoopOnlineCatalogConnector)
    assert replay.coverage is CoverageLevel.FULL_ONLINE_CATALOG
    assert replay.client.allow_full_crawl is False
    assert replay.client.max_categories == 1
    assert replay.client.max_pages_per_category == 1
    assert replay.client.allowed_context_ids == frozenset({"730400"})
    replay_audit = collection_policy_audit(replay)
    assert replay_audit is not None
    assert replay_audit.operator_opt_in is False
    assert replay_audit.store_allowlist == ("730400",)


@pytest.mark.asyncio
async def test_manual_coop_exact_collection_uses_canonical_regional_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("COOP_ALLOW_FULL_CRAWL", "true")
    monkeypatch.setenv("COOP_ONLINE_CONTEXT_IDS", "730400")

    class FakeEngine:
        disposed = False

        def dispose(self) -> None:
            self.disposed = True

    class FakeMetrics:
        def model_dump(self, *, mode: str) -> dict[str, int]:
            assert mode == "json"
            return {"products_parsed": 11_175}

    seen_scopes: list[str | None] = []

    class FakeCollector:
        def __init__(self, *_: object) -> None:
            pass

        async def collect_area(
            self,
            connector,
            area,
            *,
            auto_promote: bool,
            scope_key: str | None,
        ):  # type: ignore[no-untyped-def]
            assert isinstance(connector, CoopOnlineCatalogConnector)
            assert area.city == "Malmö"
            assert auto_promote is True
            seen_scopes.append(scope_key)
            return SimpleNamespace(
                scope_key=scope_key,
                snapshot_id="coop-snapshot",
                active_snapshot_id="coop-snapshot",
                status=SimpleNamespace(value="healthy"),
                promoted=True,
                stores=(object(),),
                metrics=FakeMetrics(),
                warnings=(),
                source_policy_audit=connector.collection_policy_audit(),
            )

    engine = FakeEngine()
    monkeypatch.setattr(
        cli,
        "_runtime",
        lambda: (SimpleNamespace(raw_snapshot_root=tmp_path), engine, object()),
    )
    monkeypatch.setattr(cli, "GroceryCollector", FakeCollector)

    exit_code = await cli._collect(
        SimpleNamespace(
            chain=Chain.COOP.value,
            city=["Malmö"],
            context_store_id="730400",
            no_promote=False,
        )
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert engine.disposed is True
    assert seen_scopes == ["coop:online:730400"]
    assert payload["results"][0]["scope_key"] == "coop:online:730400"
    assert payload["results"][0]["store_allowlist"] == ["730400"]


def test_source_policy_audit_schema_rejects_secret_like_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        SourceCollectionAudit.model_validate(
            {
                "source_policy": "review",
                "operator_opt_in": True,
                "store_allowlist": ["3211"],
                "authorization": "must-never-be-persisted",
            }
        )


def test_central_source_policy_enforcement_is_fail_closed() -> None:
    class PolicyConnector:
        def __init__(self, policy: SourcePolicy, *, opted_in: bool = False) -> None:
            self.source_policy = policy
            self.opted_in = opted_in

        def collection_policy_audit(self) -> SourceCollectionAudit:
            return SourceCollectionAudit(
                source_policy=self.source_policy,
                operator_opt_in=self.opted_in,
            )

    allowed = enforce_collection_policy(PolicyConnector(SourcePolicy.ALLOW))
    assert allowed is not None
    assert allowed.source_policy is SourcePolicy.ALLOW

    with pytest.raises(SourcePolicyError, match="REVIEW requires explicit"):
        enforce_collection_policy(PolicyConnector(SourcePolicy.REVIEW))
    reviewed = enforce_collection_policy(PolicyConnector(SourcePolicy.REVIEW, opted_in=True))
    assert reviewed is not None and reviewed.operator_opt_in is True

    with pytest.raises(SourcePolicyError, match="BLOCK forbids"):
        enforce_collection_policy(PolicyConnector(SourcePolicy.BLOCK, opted_in=True))


def test_every_production_connector_declares_source_policy() -> None:
    registry = ConnectorRegistry()
    for chain in Chain:
        connector = registry.create(chain)
        assert isinstance(connector.source_policy, SourcePolicy)
