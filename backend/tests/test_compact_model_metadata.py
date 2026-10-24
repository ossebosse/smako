"""Public supplied-field ownership and serialization must match native Pydantic."""

import copy
import json
import pickle
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

import pytest
from app.models.compact import CompactFrozenModel, _FrozenSupplied, metadata_pool_stats
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    computed_field,
    field_serializer,
    model_serializer,
)
from pydantic.warnings import PydanticDeprecatedSince20


class NativeChild(BaseModel):
    model_config = ConfigDict(frozen=True)
    amount: Decimal = Decimal("1.00")
    note: str | None = None


class CompactChild(CompactFrozenModel):
    model_config = ConfigDict(frozen=True)
    amount: Decimal = Decimal("1.00")
    note: str | None = None


class NativeParent(BaseModel):
    model_config = ConfigDict(frozen=True)
    child: NativeChild
    count: int = 3
    names: list[str] = Field(default_factory=list)
    extra: str | None = None


class CompactParent(CompactFrozenModel):
    model_config = ConfigDict(frozen=True)
    child: CompactChild
    count: int = 3
    names: list[str] = Field(default_factory=list)
    extra: str | None = None


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"exclude_unset": True},
        {"exclude_defaults": True},
        {"exclude_none": True},
        {"exclude_unset": True, "round_trip": True},
        {"exclude_unset": True, "include": {"child", "count"}},
        {"exclude_unset": True, "exclude": {"child": {"note"}}},
        {"serialize_as_any": True},
        {"exclude_unset": True, "serialize_as_any": True},
    ],
)
def test_nested_validation_and_serialization_equal_native(options):
    raw = {"child": {"amount": "2.500"}, "names": ["one"]}
    native = NativeParent.model_validate_json(json.dumps(raw))
    compact = CompactParent.model_validate_json(json.dumps(raw))
    assert type(compact.__pydantic_fields_set__) is _FrozenSupplied
    assert type(compact.child.__pydantic_fields_set__) is _FrozenSupplied
    for mode in ["python", "json"]:
        assert compact.model_dump(mode=mode, **options) == native.model_dump(mode=mode, **options)
    assert compact.model_dump_json(**options) == native.model_dump_json(**options)
    assert TypeAdapter(CompactParent).dump_json(compact, **options) == TypeAdapter(
        NativeParent
    ).dump_json(native, **options)
    assert type(compact.__pydantic_fields_set__) is _FrozenSupplied
    assert type(compact.child.__pydantic_fields_set__) is _FrozenSupplied
    assert CompactParent.model_validate(compact) is compact


def test_public_metadata_mutation_remains_owned_and_visible_after_revalidation():
    first, second = CompactChild(amount="2.50"), CompactChild(amount="2.50")
    assert first.__pydantic_fields_set__ is second.__pydantic_fields_set__
    escaped = first.model_fields_set
    assert type(escaped) is set and escaped is first.model_fields_set
    escaped.clear()
    assert first.model_dump(exclude_unset=True) == {}
    assert second.model_dump(exclude_unset=True) == {"amount": Decimal("2.50")}
    assert CompactChild.model_validate(first) is first
    escaped.add("note")
    assert first.model_dump(exclude_unset=True) == {"note": None}
    assert first == second and hash(first) == hash(second)
    assert first.__pydantic_private__ is None
    assert "_smako_fields_observed" not in type(first).model_fields
    assert "_smako_fields_observed" not in first.__dict__


@pytest.mark.parametrize(
    "operation",
    [
        copy.copy,
        copy.deepcopy,
        lambda value: value.model_copy(),
        lambda value: value.model_copy(deep=True),
        lambda value: pickle.loads(pickle.dumps(value)),
    ],
)
def test_copy_protocols_and_metadata_changes_do_not_touch_original(operation):
    original = CompactParent(child={"amount": "3.00"}, names=["one"])
    copied = operation(original)
    assert copied is not original
    assert copied.model_dump(exclude_unset=True) == original.model_dump(exclude_unset=True)
    copied.model_fields_set.clear()
    assert copied.model_dump(exclude_unset=True) == {}
    assert original.model_dump(exclude_unset=True) == {
        "child": {"amount": Decimal("3.00")},
        "names": ["one"],
    }
    changed = original.model_copy(update={"count": 7}, deep=True)
    assert changed.count == 7 and original.count == 3
    assert changed.model_dump(exclude_unset=True)["count"] == 7
    changed.names.append("copy")
    assert original.names == ["one"]


def test_construct_preserves_external_metadata_alias_and_normal_validation_stays_strict():
    fields = {"amount"}
    first = CompactChild.model_construct(_fields_set=fields, amount=Decimal("2.00"))
    second = CompactChild.model_construct(_fields_set=fields, amount=Decimal("4.00"))
    assert first.model_fields_set is fields and second.model_fields_set is fields
    fields.clear()
    assert first.model_dump(exclude_unset=True) == second.model_dump(exclude_unset=True) == {}
    assert CompactChild.model_validate(first) is first
    fields.add("note")
    assert first.model_dump(exclude_unset=True) == {"note": None}
    a, b, restored = pickle.loads(pickle.dumps((first, second, fields)))
    assert a.model_fields_set is b.model_fields_set is restored
    with pytest.raises(ValidationError):
        CompactChild(amount="invalid decimal")


def test_unknown_copy_fields_and_custom_serializers_keep_native_metadata():
    copied = CompactChild().model_copy(update={"unknown_field": 4})
    assert type(copied.__pydantic_fields_set__) is set
    assert copied.model_fields_set == {"unknown_field"}

    class Custom(CompactFrozenModel):
        model_config = ConfigDict(frozen=True)
        amount: int

        @model_serializer
        def custom(self):
            return {"value": self.amount}

    value = Custom(amount=7)
    assert type(value.__pydantic_fields_set__) is set
    assert value.model_dump(exclude_unset=True) == {"value": 7}


def test_nonfrozen_and_revalidated_classes_keep_native_metadata():
    class Mutable(CompactFrozenModel):
        value: int = 1

    class Revalidated(CompactFrozenModel):
        model_config = ConfigDict(frozen=True, revalidate_instances="always")
        value: int = 1

    for cls in (Mutable, Revalidated):
        value = cls(value=2)
        assert type(value.__pydantic_fields_set__) is set
        assert cls.model_validate(value).value == 2


def test_deprecated_metadata_and_copy_preserve_native_behavior():
    value = CompactChild(amount="2")
    with pytest.warns(PydanticDeprecatedSince20):
        fields = value.__fields_set__
    fields.clear()
    assert value.model_dump(exclude_unset=True) == {}
    with pytest.warns(PydanticDeprecatedSince20):
        copied = value.copy(update={"note": "copied"})
    assert copied.model_dump(exclude_unset=True) == {"note": "copied"}


def test_concurrent_public_reads_return_the_same_owned_set():
    value = CompactChild(amount="8")
    barrier = Barrier(8)

    def read(_):
        barrier.wait()
        return value.model_fields_set

    with ThreadPoolExecutor(max_workers=8) as pool:
        fields = list(pool.map(read, range(8)))
    assert all(item is fields[0] for item in fields)
    assert type(fields[0]) is set
    assert metadata_pool_stats()["bytes"] <= metadata_pool_stats()["maximum_bytes"]


def test_full_pool_falls_back_without_changing_values(monkeypatch):
    from app.models import compact

    monkeypatch.setattr(compact, "MAX_PATTERNS", 0)

    class NewPattern(CompactFrozenModel):
        model_config = ConfigDict(frozen=True)
        previously_unseen_pool_probe: int

    value = NewPattern(previously_unseen_pool_probe=2)
    assert type(value.__pydantic_fields_set__) is set
    assert value.model_dump(exclude_unset=True) == {"previously_unseen_pool_probe": 2}


def test_identity_dependent_custom_hooks_keep_native_metadata():
    class Computed(CompactFrozenModel):
        model_config = ConfigDict(frozen=True)
        value: int = 1

        @computed_field
        @property
        def identity(self) -> int:
            return id(self)

    class Serialized(CompactFrozenModel):
        model_config = ConfigDict(frozen=True)
        value: int

        @field_serializer("value")
        def identity(self, value):
            return id(self)

    class CopyHook(CompactFrozenModel):
        model_config = ConfigDict(frozen=True)
        value: int

        def __copy__(self):
            raise AssertionError("Serialization cannot invoke a custom copy hook")

    for cls in (Computed, Serialized, CopyHook):
        value = cls(value=2)
        assert type(value.__pydantic_fields_set__) is set
        output = value.model_dump(exclude_unset=True)
        if cls is Computed:
            assert output["identity"] == id(value)
        elif cls is Serialized:
            assert output["value"] == id(value)
        else:
            assert output == {"value": 2}
