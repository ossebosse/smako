from __future__ import annotations

from typing import cast

from grocery_data.app.domain import Chain, CoverageLevel
from grocery_data.app.services.collector import _uses_ica_offer_registry
from grocery_data.app.storage.models import StoreModel


def _store(coverage: CoverageLevel) -> StoreModel:
    return cast(
        StoreModel,
        type(
            "PersistedStoreShape",
            (),
            {"chain": Chain.ICA.value, "coverage": coverage.value},
        )(),
    )


def test_full_ica_online_catalog_does_not_enter_legacy_offer_registry() -> None:
    assert _uses_ica_offer_registry(_store(CoverageLevel.OFFERS_ONLY)) is True
    assert _uses_ica_offer_registry(_store(CoverageLevel.PARTIAL_CATALOG)) is False
    assert _uses_ica_offer_registry(_store(CoverageLevel.FULL_ONLINE_CATALOG)) is False
