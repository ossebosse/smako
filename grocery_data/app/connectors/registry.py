from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, model_validator

from grocery_data.app.connectors.base import GroceryConnector
from grocery_data.app.connectors.citygross import CityGrossConnector
from grocery_data.app.connectors.coop import CoopConnector
from grocery_data.app.connectors.hemkop import HemkopConnector
from grocery_data.app.connectors.ica import IcaConnector
from grocery_data.app.connectors.lidl import LidlConnector
from grocery_data.app.connectors.willys import WillysConnector
from grocery_data.app.domain import Chain, CoverageLevel
from grocery_data.app.domain.enums import DEFAULT_SOURCE_CHAINS


class ConnectorDescriptor(BaseModel):
    model_config = ConfigDict(frozen=True)

    chain: Chain
    source_coverage: CoverageLevel
    implemented: bool
    acceptance_contract_passed: bool = False
    missing_acceptance_checks: tuple[str, ...] = ()
    limitation: str | None = None

    @model_validator(mode="after")
    def implemented_requires_acceptance(self) -> ConnectorDescriptor:
        if self.acceptance_contract_passed and self.missing_acceptance_checks:
            raise ValueError("accepted connector cannot have missing acceptance checks")
        if self.implemented and not self.acceptance_contract_passed:
            raise ValueError("implemented connector must pass its coverage acceptance contract")
        return self


SOURCE_COVERAGE: dict[Chain, ConnectorDescriptor] = {
    Chain.ICA: ConnectorDescriptor(
        chain=Chain.ICA,
        source_coverage=CoverageLevel.OFFERS_ONLY,
        implemented=True,
        acceptance_contract_passed=True,
        limitation=(
            "Public store-specific offers remain the accepted OWN production source. "
            "The current v6 online surface has a separate PARTIAL_CATALOG connector "
            "with exact region context, category, continuation and batched-decoration "
            "contracts plus a strict ephemeral-browser transport, but the ordinary "
            "Chromium acceptance run stopped on an ICA API HTTP 405 text/html "
            "challenge/CAPTCHA response "
            "before one category/full traversal could be reconciled. It is therefore "
            "not basket eligible and ICA's basket default remains Primat."
        ),
    ),
    Chain.COOP: ConnectorDescriptor(
        chain=Chain.COOP,
        source_coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        implemented=True,
        acceptance_contract_passed=True,
        limitation=(
            "FULL_ONLINE_CATALOG is verified for the regional Coop Online Syd "
            "fulfillment context 730400. Its prices are online prices, not verified "
            "physical shelf prices. Live full collection remains REVIEW-gated by "
            "COOP_ALLOW_FULL_CRAWL and an exact COOP_ONLINE_CONTEXT_IDS allowlist. "
            "The ordinary registry factory remains the bounded physical-offers source."
        ),
    ),
    Chain.WILLYS: ConnectorDescriptor(
        chain=Chain.WILLYS,
        source_coverage=CoverageLevel.FULL_CATALOG,
        implemented=True,
        acceptance_contract_passed=True,
    ),
    Chain.HEMKOP: ConnectorDescriptor(
        chain=Chain.HEMKOP,
        source_coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        implemented=True,
        acceptance_contract_passed=True,
        limitation=(
            "FULL_ONLINE_CATALOG is verified for the activated Malmö Triangeln "
            "online-store context (storeId 4247). Source policy remains REVIEW: "
            "a live full collection requires explicit HEMKOP_ALLOW_FULL_CRAWL=true "
            "and an exact store allowlist. The accepted offline replay snapshot is "
            "promoted; the original live source snapshot remains inactive evidence."
        ),
    ),
    Chain.LIDL: ConnectorDescriptor(
        chain=Chain.LIDL,
        source_coverage=CoverageLevel.OFFERS_ONLY,
        implemented=True,
        acceptance_contract_passed=True,
        limitation=(
            "The public source exposes an exactly traversable current/upcoming "
            "published-product and offer surface, not a complete local store catalog. "
            "Prices belong to an unselected public default-region context and are never "
            "assigned to a physical Lidl store."
        ),
    ),
    Chain.CITY_GROSS: ConnectorDescriptor(
        chain=Chain.CITY_GROSS,
        source_coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        implemented=True,
        acceptance_contract_passed=True,
        limitation=(
            "FULL_ONLINE_CATALOG is verified for Malmö Hyllie (storeNumber 3211). "
            "Source policy remains REVIEW: a live full collection requires explicit "
            "CITYGROSS_ALLOW_FULL_CRAWL=true and an exact store allowlist. No City Gross "
            "store or home-delivery context is verified for Lund."
        ),
    ),
}


class ConnectorRegistry:
    def __init__(self) -> None:
        self._factories: dict[Chain, Callable[[], GroceryConnector]] = {
            Chain.COOP: CoopConnector,
            # Registry creation is deliberately bounded and inert.  The CLI's
            # collection path must call ``for_full_collection`` so a descriptor
            # lookup can never bypass the REVIEW opt-in or store allowlist.
            Chain.CITY_GROSS: CityGrossConnector.for_bounded_discovery,
            Chain.HEMKOP: HemkopConnector.for_bounded_discovery,
            Chain.ICA: IcaConnector,
            Chain.LIDL: LidlConnector.for_bounded_discovery,
            Chain.WILLYS: WillysConnector,
        }

    def create(self, chain: Chain) -> GroceryConnector:
        factory = self._factories.get(chain)
        if factory is None:
            descriptor = SOURCE_COVERAGE.get(chain)
            if descriptor is None:
                raise NotImplementedError(f"{chain.value} is not enabled in the default connector registry")
            raise NotImplementedError(
                f"{chain.value} connector is not implemented: {descriptor.limitation}"
            )
        return factory()

    def descriptors(self) -> tuple[ConnectorDescriptor, ...]:
        return tuple(SOURCE_COVERAGE[chain] for chain in DEFAULT_SOURCE_CHAINS)
