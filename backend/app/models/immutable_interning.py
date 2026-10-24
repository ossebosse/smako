"""Validation-scoped sharing of equal, recursively frozen model values.

The pool dies with one artifact parse. Mutable lists/dictionaries, private
state, and models with mutable fields are never interned. Exact equality is
checked even on a hash collision; supplied-field sets remain distinct.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from sys import getsizeof

from pydantic import BaseModel

_ACTIVE = ContextVar("artifact_immutable_models", default=None)
MAX_MODELS = 65536
MAX_POOL_BYTES = 32 * 1024 * 1024


class _ReadOnlyFieldsSet(set):
    """Set-compatible serializer metadata; copies belong to the new model.

    Pydantic's pinned serializer requires a set (not a frozenset). Its copy
    paths expect a fresh mutable set, including before model_copy updates.
    """
    __slots__ = ()

    def __new__(cls, values=()):
        result = super().__new__(cls)
        set.update(result, values)
        return result

    def __init__(self, values=()):
        pass

    def copy(self):
        return set(self)

    def __copy__(self):
        return set(self)

    def __deepcopy__(self, memo):
        return set(self)

    def _readonly(self, *args, **kwargs):
        raise TypeError("Parsed artifact supplied-field metadata is read-only; copy the model before editing")

    add = clear = difference_update = discard = intersection_update = _readonly
    pop = remove = symmetric_difference_update = update = _readonly
    __ior__ = __iand__ = __isub__ = __ixor__ = _readonly


def _metadata_bytes(value):
    if isinstance(value, type):
        return 0  # Existing model/primitive classes are not owned by the pool.
    return getsizeof(value) + (sum(_metadata_bytes(v) for v in value) if isinstance(value, tuple) else 0)


class _Pool:
    def __init__(self, *, freeze_fields=False, intern_models=True):
        self.values = {}
        self.field_sets = {}
        self.freeze_fields = freeze_fields
        self.intern_models = intern_models
        self.field_set_hits = 0
        self.count = self.hits = self.retained_bytes = 0

    def share_fields(self, value):
        if not self.freeze_fields or not value.model_config.get("frozen"):
            return value
        supplied = value.model_fields_set
        if isinstance(supplied, _ReadOnlyFieldsSet):
            return value
        key = tuple(sorted(supplied))
        shared = self.field_sets.get(key)
        if shared is None:
            shared = _ReadOnlyFieldsSet(supplied)
            size = _metadata_bytes(key) + getsizeof(shared) + 256
            if self.retained_bytes + size > MAX_POOL_BYTES:
                return value
            self.field_sets[key] = shared
            self.retained_bytes += size
        else:
            self.field_set_hits += 1
        # Enabled only while parsing JSON: this newly created model has no
        # outside owner. Python-mode validation never mutates caller models.
        object.__setattr__(value, "__pydantic_fields_set__", shared)
        return value

    def visit(self, value):
        # Python equality collapses some distinct serialized values (UTC vs
        # another offset, Decimal scale, and signed zero). Bind those exact
        # representations as well as model equality before sharing evidence.
        if isinstance(value, datetime):
            return value, True, (datetime, value.isoformat(), value.fold)
        if isinstance(value, date):
            return value, True, (date, value.isoformat())
        if isinstance(value, Decimal):
            return value, True, (Decimal, value.as_tuple())
        if isinstance(value, float):
            return value, True, (float, value.hex())
        if isinstance(value, Enum):
            return value, True, (type(value), value.value)
        if isinstance(value, (str, bytes, int, bool)) or value is None:
            return value, True, None
        if isinstance(value, (tuple, list)):
            rows = [self.visit(child) for child in value]
            changed = any(row[0] is not child for row, child in zip(rows, value, strict=True))
            result = type(value)(row[0] for row in rows) if changed else value
            metadata = tuple((index, row[2]) for index, row in enumerate(rows) if row[2] is not None)
            return result, isinstance(value, tuple) and all(row[1] for row in rows), metadata or None
        if not isinstance(value, BaseModel) or not value.model_config.get("frozen"):
            return value, False, None
        if value.__pydantic_private__ or value.__pydantic_extra__:
            return value, False, None
        value = self.share_fields(value)
        updates, children, immutable, supplied_mask = {}, [], True, 0
        supplied = value.model_fields_set
        for position, name in enumerate(type(value).model_fields):
            if name in supplied:
                supplied_mask |= 1 << position
            child = getattr(value, name)
            shared, safe, identity = self.visit(child)
            immutable = immutable and safe
            if shared is not child:
                updates[name] = shared
            if identity is not None:
                children.append((name, identity))
        if updates:
            value = value.model_copy(update=updates)
            # model_copy adds update keys to the supplied-field set. Sharing
            # defaults must preserve exclude_unset serialization as well.
            object.__setattr__(value, "__pydantic_fields_set__",
                               supplied if isinstance(supplied, _ReadOnlyFieldsSet) else set(supplied))
        if not immutable or not self.intern_models:
            return value, immutable, id(value) if immutable else None
        unknown_fields = tuple(sorted(supplied - type(value).model_fields.keys()))
        key = type(value), hash(value), supplied_mask, unknown_fields, tuple(children)
        bucket = self.values.get(key, ())
        for existing in bucket:
            if existing == value:
                self.hits += 1
                return existing, True, id(existing)
        # Values are already owned by the parsed artifact. Budget the pool's
        # additional keys/metadata plus conservative dict/list entry overhead;
        # no second evidence graph is retained outside this validation scope.
        size = _metadata_bytes(key) + 256
        if self.count < MAX_MODELS and self.retained_bytes + size <= MAX_POOL_BYTES:
            self.values.setdefault(key, []).append(value)
            self.count += 1
            self.retained_bytes += size
        return value, True, id(value)


@contextmanager
def immutable_model_pool(*, freeze_fields=False, intern_models=True):
    pool = _Pool(freeze_fields=freeze_fields, intern_models=intern_models)
    token = _ACTIVE.set(pool)
    try:
        yield pool
    finally:
        _ACTIVE.reset(token)


def share_frozen_models(value):
    pool = _ACTIVE.get()
    return pool.visit(value)[0] if pool is not None else value


def share_supplied_fields(value):
    pool = _ACTIVE.get()
    return pool.share_fields(value) if pool is not None else value
