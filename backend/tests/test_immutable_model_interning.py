"""Exact immutable evidence sharing must preserve values and mutable ownership."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from app.models import immutable_interning as interning
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from backend.tests.test_price_universe_runtime import _build_prepared


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)
    value: str = "default"

    def __hash__(self):
        return 1  # Deliberate collisions cannot merge different evidence.


class MutableFields(BaseModel):
    model_config = ConfigDict(frozen=True)
    values: list[str] = Field(default_factory=list)
    _private: list[str] = PrivateAttr(default_factory=list)


def test_pool_keeps_collision_values_supplied_fields_and_scope_distinct():
    with interning.immutable_model_pool():
        first = interning.share_frozen_models(Frozen(value="one"))
        assert interning.share_frozen_models(Frozen(value="one")) is first
        assert interning.share_frozen_models(Frozen(value="two")) != first
        implicit = interning.share_frozen_models(Frozen())
        explicit = interning.share_frozen_models(Frozen(value="default"))
        assert implicit is not explicit
        assert implicit.model_dump(exclude_unset=True) == {}
        assert explicit.model_dump(exclude_unset=True) == {"value": "default"}
    assert interning.share_frozen_models(Frozen(value="one")) is not first


def test_mutable_containers_and_private_state_never_become_shared():
    with interning.immutable_model_pool():
        first = interning.share_frozen_models(MutableFields(values=["one"]))
        second = interning.share_frozen_models(MutableFields(values=["one"]))
        first.values.append("changed")
        first._private.append("private")
        assert second.values == ["one"] and second._private == []
        left = interning.share_frozen_models([Frozen(value="one")])
        right = interning.share_frozen_models([Frozen(value="one")])
        assert left is not right and left[0] is right[0]


def test_pool_capacity_falls_back_to_unshared_equal_values(monkeypatch):
    monkeypatch.setattr(interning, "MAX_MODELS", 1)
    with interning.immutable_model_pool() as pool:
        interning.share_frozen_models(Frozen(value="first"))
        other = interning.share_frozen_models(Frozen(value="other"))
        again = interning.share_frozen_models(Frozen(value="other"))
        assert other == again and other is not again
        assert pool.count == 1


@pytest.mark.asyncio
async def test_real_artifact_preserves_wire_content_and_owns_mutable_offer_lists():
    _, prepared, _, _ = await _build_prepared()
    raw = prepared.to_artifact().model_dump_json()
    shared = PreparedPriceUniverseArtifact.model_validate_json(raw)

    @contextmanager
    def no_pool():
        yield SimpleNamespace(hits=0)

    with patch.object(interning, "immutable_model_pool", no_pool):
        unshared = PreparedPriceUniverseArtifact.model_validate_json(raw)
    assert shared.model_dump_json() == unshared.model_dump_json()
    candidates = [candidate for rows in (shared.canonical_candidates,
        shared.semantic_canonical_candidates, shared.matched_canonical_candidates)
        for row in rows for candidate in row.candidates]
    pairs = [(a, b) for index, a in enumerate(candidates) for b in candidates[index + 1:]
             if a.source_provenance == b.source_provenance and a.source_provenance is not None]
    assert pairs
    for first, second in pairs:
        assert first.source_provenance is second.source_provenance
        assert first.offers is not second.offers
