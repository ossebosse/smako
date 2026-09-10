"""Deterministic structural fingerprints for saved JSON payloads.

Fingerprints intentionally contain paths and JSON types only. Values, headers,
cookies, and other request material never become part of the fingerprint.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_SIMPLE_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class JsonType(StrEnum):
    NULL = "null"
    BOOLEAN = "boolean"
    NUMBER = "number"
    STRING = "string"
    ARRAY = "array"
    OBJECT = "object"


_TYPE_ORDER = {kind: index for index, kind in enumerate(JsonType)}


class SchemaFingerprint(BaseModel):
    """A stable digest plus the evidence needed to explain it."""

    model_config = ConfigDict(frozen=True)

    digest: str = Field(min_length=64, max_length=64)
    paths: dict[str, tuple[JsonType, ...]]

    @property
    def fingerprint(self) -> str:
        """Compatibility-friendly name for consumers that call the digest a fingerprint."""

        return self.digest


class SchemaTypeChange(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str
    old_types: tuple[JsonType, ...]
    new_types: tuple[JsonType, ...]


class SchemaDiff(BaseModel):
    model_config = ConfigDict(frozen=True)

    added: tuple[str, ...] = ()
    removed: tuple[str, ...] = ()
    type_changed: tuple[SchemaTypeChange, ...] = ()

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.type_changed)

    @property
    def changed_paths(self) -> tuple[str, ...]:
        changed = {change.path for change in self.type_changed}
        return tuple(sorted({*self.added, *self.removed, *changed}))


def _json_type(value: Any) -> JsonType:
    if value is None:
        return JsonType.NULL
    if isinstance(value, bool):
        return JsonType.BOOLEAN
    if isinstance(value, (int, float)):
        return JsonType.NUMBER
    if isinstance(value, str):
        return JsonType.STRING
    if isinstance(value, list):
        return JsonType.ARRAY
    if isinstance(value, Mapping):
        return JsonType.OBJECT
    raise TypeError(f"unsupported non-JSON value: {type(value).__name__}")


def _child_path(parent: str, key: str) -> str:
    if _SIMPLE_KEY.fullmatch(key):
        return f"{parent}.{key}"
    encoded = json.dumps(key, ensure_ascii=False, separators=(",", ":"))
    return f"{parent}[{encoded}]"


def collect_schema_paths(payload: Any) -> dict[str, tuple[JsonType, ...]]:
    """Collect path/type unions without retaining any source values.

    Array indices are represented as ``[]`` so record ordering and array length
    do not perturb a schema fingerprint.
    """

    observed: dict[str, set[JsonType]] = {}

    def walk(value: Any, path: str) -> None:
        value_type = _json_type(value)
        observed.setdefault(path, set()).add(value_type)
        if isinstance(value, Mapping):
            for key in sorted(value):
                if not isinstance(key, str):
                    raise TypeError("JSON object keys must be strings")
                walk(value[key], _child_path(path, key))
        elif isinstance(value, list):
            item_path = f"{path}[]"
            for item in value:
                walk(item, item_path)

    walk(payload, "$")
    return {
        path: tuple(sorted(types, key=_TYPE_ORDER.__getitem__))
        for path, types in sorted(observed.items())
    }


def fingerprint_json(payload: Any) -> SchemaFingerprint:
    """Build a stable SHA-256 fingerprint from JSON paths and basic types."""

    paths = collect_schema_paths(payload)
    canonical = {path: [value_type.value for value_type in types] for path, types in paths.items()}
    encoded = json.dumps(
        canonical,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return SchemaFingerprint(digest=hashlib.sha256(encoded).hexdigest(), paths=paths)


def diff_fingerprints(old: SchemaFingerprint, new: SchemaFingerprint) -> SchemaDiff:
    """Explain structural changes between two fingerprints."""

    old_paths = set(old.paths)
    new_paths = set(new.paths)
    type_changed = tuple(
        SchemaTypeChange(
            path=path,
            old_types=old.paths[path],
            new_types=new.paths[path],
        )
        for path in sorted(old_paths & new_paths)
        if old.paths[path] != new.paths[path]
    )
    return SchemaDiff(
        added=tuple(sorted(new_paths - old_paths)),
        removed=tuple(sorted(old_paths - new_paths)),
        type_changed=type_changed,
    )


def diff_json_schemas(old_payload: Any, new_payload: Any) -> SchemaDiff:
    return diff_fingerprints(fingerprint_json(old_payload), fingerprint_json(new_payload))


# Short aliases make the API natural both in collectors and replay tools.
schema_fingerprint = fingerprint_json
diff_schema = diff_json_schemas
