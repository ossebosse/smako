"""Compact supplied-field metadata while preserving Pydantic's public set API.

Only schema field names are pooled. Domain values/validation are untouched.
A public metadata read materializes an owned native set; exclusion serializers
use a temporary shallow copy, never mutate the original model's metadata.
"""

from __future__ import annotations

import sys
from contextvars import ContextVar
from threading import Lock
from typing import Any

from pydantic import BaseModel, SerializationInfo, SerializerFunctionWrapHandler, model_serializer

MAX_PATTERNS = 256
MAX_FIELD_NAMES = 128
MAX_POOL_BYTES = 1024 * 1024
_POOL = {}
_POOL_BYTES = 0
_POOL_LOCK = Lock()
_OWNERSHIP_LOCK = Lock()
_EXTERNAL_CONSTRUCT = ContextVar("external_supplied_fields", default=False)
# These existing getters read values only. Unknown computed/field serializers
# may depend on instance identity or mutate private state, so keep native
# metadata rather than invoking them on a temporary serialization copy.
_PURE_COMPUTED = frozenset(
    {
        ("app.models.product", "Product.global_identity"),
        ("app.models.product", "Product.normalized_unit_price"),
        ("app.models.product", "Product.normalized_unit"),
        ("app.models.product", "ProductCandidate.global_identity"),
    }
)


class _FrozenSupplied(frozenset):
    __slots__ = ()

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


def _observed(model):
    try:
        return object.__getattribute__(model, "_smako_fields_observed")
    except AttributeError:
        return False


def _compact(model):
    global _POOL_BYTES
    cls = type(model)
    if (
        cls.model_config.get("frozen") is not True
        or cls.model_config.get("revalidate_instances", "never") != "never"
        or _EXTERNAL_CONSTRUCT.get()
        or _observed(model)
    ):
        return
    serializers = cls.__pydantic_decorators__.model_serializers
    if (
        len(serializers) != 1
        or "_serialize_compact_fields" not in serializers
        or serializers["_serialize_compact_fields"].func
        is not CompactFrozenModel._serialize_compact_fields
    ):
        return  # Custom serializers retain ordinary native metadata.
    if (
        cls.__pydantic_decorators__.field_serializers
        or cls.__copy__ is not CompactFrozenModel.__copy__
        or any(
            (item.func.__module__, item.func.__qualname__) not in _PURE_COMPUTED
            for item in cls.__pydantic_decorators__.computed_fields.values()
        )
    ):
        return
    fields = model.__pydantic_fields_set__
    if (
        type(fields) is not set
        or len(fields) > MAX_FIELD_NAMES
        or any(
            type(name) is not str or len(name) > 128 or name not in cls.model_fields
            for name in fields
        )
    ):
        return
    key = _FrozenSupplied(fields)
    shared = _POOL.get(key)
    if shared is None:
        with _POOL_LOCK:
            shared = _POOL.get(key)
            if shared is None:
                size = sys.getsizeof(key) + sum(sys.getsizeof(name) for name in key)
                # Reserve dictionary growth as well as immutable set tables.
                if len(_POOL) >= MAX_PATTERNS or _POOL_BYTES + size + 32768 > MAX_POOL_BYTES:
                    return
                _POOL[key] = key
                _POOL_BYTES += size
                shared = key
    with _OWNERSHIP_LOCK:
        if not _observed(model):
            object.__setattr__(model, "__pydantic_fields_set__", shared)


def metadata_pool_stats():
    with _POOL_LOCK:
        return {
            "patterns": len(_POOL),
            "bytes": _POOL_BYTES + sys.getsizeof(_POOL),
            "maximum_patterns": MAX_PATTERNS,
            "maximum_bytes": MAX_POOL_BYTES,
        }


class CompactFrozenModel(BaseModel):
    # A slot is not a Pydantic private attribute or field: it cannot affect
    # value equality, hashing, validation or serialized domain content.
    __slots__ = ("_smako_fields_observed",)

    def model_post_init(self, context: Any) -> None:
        super().model_post_init(context)
        _compact(self)

    @property
    def model_fields_set(self) -> set[str]:
        with _OWNERSHIP_LOCK:
            fields = self.__pydantic_fields_set__
            if type(fields) is _FrozenSupplied:
                fields = set(fields)
                object.__setattr__(self, "__pydantic_fields_set__", fields)
            object.__setattr__(self, "_smako_fields_observed", True)
            return fields

    @property
    def __fields_set__(self) -> set[str]:
        # Preserve Pydantic's deprecated-access warning as well as mutation.
        _ = super().__fields_set__
        return self.model_fields_set

    def __copy__(self):
        copied = super().__copy__()
        if type(copied.__pydantic_fields_set__) is _FrozenSupplied:
            object.__setattr__(
                copied, "__pydantic_fields_set__", set(copied.__pydantic_fields_set__)
            )
        return copied

    def __deepcopy__(self, memo=None):
        copied = super().__deepcopy__(memo)
        if type(copied.__pydantic_fields_set__) is _FrozenSupplied:
            object.__setattr__(
                copied, "__pydantic_fields_set__", set(copied.__pydantic_fields_set__)
            )
        return copied

    def model_copy(self, *, update=None, deep=False):
        copied = super().model_copy(update=update, deep=deep)
        _compact(copied)
        return copied

    def copy(self, *, include=None, exclude=None, update=None, deep=False):
        _ = self.model_fields_set  # Native metadata for the deprecated copy machinery.
        return super().copy(include=include, exclude=exclude, update=update, deep=deep)

    @classmethod
    def model_construct(cls, _fields_set=None, **values):
        # An explicitly supplied native set belongs to the caller and can be
        # aliased intentionally. Preserve it through post-init and thereafter.
        token = _EXTERNAL_CONSTRUCT.set(_fields_set is not None)
        try:
            model = super().model_construct(_fields_set=_fields_set, **values)
        finally:
            _EXTERNAL_CONSTRUCT.reset(token)
        if _fields_set is not None:
            object.__setattr__(model, "_smako_fields_observed", True)
        return model

    def __setstate__(self, state):
        super().__setstate__(state)
        object.__setattr__(self, "_smako_fields_observed", True)

    @model_serializer(mode="wrap")
    def _serialize_compact_fields(
        self, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ):
        if info.exclude_unset and type(self.__pydantic_fields_set__) is _FrozenSupplied:
            return handler(self.__copy__())
        return handler(self)
