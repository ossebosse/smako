from __future__ import annotations

from typing import Protocol, runtime_checkable

from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    GeographicArea,
    ProductParseResult,
    RawBatch,
    SourceCollectionAudit,
    SourcePolicy,
    SourceStore,
)


class ConnectorFetchError(RuntimeError):
    """A connector operation aborted after zero or more raw responses arrived.

    The partial batch is deliberately part of the exception contract so the
    collector can persist evidence before rejecting the candidate snapshot.
    """

    def __init__(self, message: str, *, partial_batch: RawBatch) -> None:
        super().__init__(message)
        self.partial_batch = partial_batch


class SourcePolicyError(RuntimeError):
    """Collection was denied by the connector's declared source policy."""


def collection_policy_audit(connector: object) -> SourceCollectionAudit | None:
    """Read only the closed, sanitized policy-audit contract from a connector."""

    declared_value = getattr(connector, "source_policy", None)
    declared = SourcePolicy(declared_value) if declared_value is not None else None
    provider = getattr(connector, "collection_policy_audit", None)
    if provider is None:
        if declared is None:
            return None
        return SourceCollectionAudit(
            source_policy=declared,
            operator_opt_in=False,
        )
    if not callable(provider):
        raise TypeError("collection_policy_audit must be callable")
    value = provider()
    audit = (
        value
        if isinstance(value, SourceCollectionAudit)
        else SourceCollectionAudit.model_validate(value)
    )
    if declared is not None and audit.source_policy is not declared:
        raise SourcePolicyError(
            "connector source_policy disagrees with its collection policy audit"
        )
    return audit


def enforce_collection_policy(connector: object) -> SourceCollectionAudit | None:
    """Fail before fetch when a declared policy does not permit collection."""

    audit = collection_policy_audit(connector)
    if audit is None:
        # Legacy/test connectors without policy metadata remain compatible.
        # Every production chain connector declares a policy explicitly.
        return None
    if audit.source_policy is SourcePolicy.BLOCK:
        raise SourcePolicyError("source policy BLOCK forbids collection")
    if audit.source_policy is SourcePolicy.REVIEW and not audit.operator_opt_in:
        raise SourcePolicyError("source policy REVIEW requires explicit operator opt-in")
    return audit


@runtime_checkable
class GroceryConnector(Protocol):
    """Raw-first connector contract shared by all chain implementations."""

    chain: Chain
    coverage: CoverageLevel
    connector_version: str
    parser_version: str
    source_policy: SourcePolicy

    async def fetch_stores(self, area: GeographicArea) -> RawBatch: ...

    def parse_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
    ) -> list[SourceStore]: ...

    def catalog_eligible(self, store: SourceStore) -> bool:
        """Return whether this connector can prove a catalog context for the store."""
        ...

    async def fetch_catalog(self, store: SourceStore) -> RawBatch: ...

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult: ...

    async def fetch_offers(self, store: SourceStore) -> RawBatch: ...

    async def aclose(self) -> None: ...
