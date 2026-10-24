"""Exact immutable evidence sharing must preserve values and mutable ownership."""
from contextlib import contextmanager
from copy import copy, deepcopy
from datetime import datetime
from decimal import Decimal
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


def test_pool_byte_budget_falls_back_without_retaining_keys(monkeypatch):
    monkeypatch.setattr(interning, "MAX_POOL_BYTES", 0)
    with interning.immutable_model_pool() as pool:
        first = interning.share_frozen_models(Frozen(value="same"))
        second = interning.share_frozen_models(Frozen(value="same"))
        assert first == second and first is not second
        assert pool.count == pool.retained_bytes == 0


def test_equal_python_values_with_different_serialization_remain_distinct():
    class Evidence(BaseModel):
        model_config = ConfigDict(frozen=True)
        observed: datetime
        amount: Decimal
        number: float

    values = [Evidence(observed=datetime.fromisoformat(clock), amount=Decimal(amount), number=number)
              for clock, amount, number in [
                  ("2026-10-24T08:00:00+02:00", "1.00", 0.0),
                  ("2026-10-24T06:00:00+00:00", "1.00", 0.0),
                  ("2026-10-24T08:00:00+02:00", "1.0", 0.0),
                  ("2026-10-24T08:00:00+02:00", "1.00", -0.0)]]
    assert all(value == values[0] for value in values)
    with interning.immutable_model_pool():
        shared = [interning.share_frozen_models(value) for value in values]
    assert len({id(value) for value in shared}) == len(values)
    assert [value.model_dump_json() for value in shared] == [value.model_dump_json() for value in values]


@pytest.mark.asyncio
async def test_real_artifact_preserves_wire_content_and_owns_mutable_offer_lists():
    _, prepared, _, _ = await _build_prepared()
    raw = prepared.to_artifact().model_dump_json()
    shared = PreparedPriceUniverseArtifact.model_validate_json(raw)

    @contextmanager
    def no_pool(**kwargs):
        yield SimpleNamespace(hits=0)

    with patch.object(interning, "immutable_model_pool", no_pool):
        unshared = PreparedPriceUniverseArtifact.model_validate_json(raw)
    assert shared.model_dump_json() == unshared.model_dump_json()
    assert shared.model_dump_json(exclude_unset=True) == unshared.model_dump_json(exclude_unset=True)
    assert type(prepared.universe.products[0].model_fields_set) is set
    candidates = [candidate for rows in (shared.canonical_candidates,
        shared.semantic_canonical_candidates, shared.matched_canonical_candidates)
        for row in rows for candidate in row.candidates]
    pairs = [(a, b) for index, a in enumerate(candidates) for b in candidates[index + 1:]
             if a.source_provenance == b.source_provenance and a.source_provenance is not None]
    assert pairs
    for first, second in pairs:
        assert first.source_provenance is not second.source_provenance
        assert first.source_provenance.model_fields_set is second.source_provenance.model_fields_set
        assert first.offers is not second.offers
    original = shared.universe.products[0]
    expected = original.model_dump_json(exclude_unset=True)
    with pytest.raises(TypeError, match="read-only"):
        original.model_fields_set.add("unreviewed")
    for cloned in (copy(original), deepcopy(original), original.model_copy(), original.model_copy(deep=True)):
        assert cloned.model_dump_json(exclude_unset=True) == expected
        assert type(cloned.model_fields_set) is set
        cloned.model_fields_set.add("unreviewed")
        assert "unreviewed" not in original.model_fields_set
    updated = original.model_copy(update={"store_name": "New isolated test name"})
    assert "store_name" in updated.model_fields_set
    assert original.model_dump_json(exclude_unset=True) == expected
