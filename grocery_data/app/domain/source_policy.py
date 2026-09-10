from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from grocery_data.app.domain.enums import SourcePolicy


class SourceCollectionAudit(BaseModel):
    """Sanitized, explicitly bounded source-policy evidence for one run.

    The closed schema is intentional: connectors cannot accidentally persist
    cookies, headers, tokens or personal context through this audit channel.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_policy: SourcePolicy
    operator_opt_in: bool
    store_allowlist: tuple[str, ...] = ()
    requests_per_second: float | None = Field(default=None, gt=0)
    max_concurrency: int | None = Field(default=None, ge=1)

    @field_validator("store_allowlist")
    @classmethod
    def sorted_public_context_ids(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(str(value).strip() for value in values)
        if any(not value for value in normalized):
            raise ValueError("store allowlist values must be non-empty")
        if len(set(normalized)) != len(normalized):
            raise ValueError("store allowlist values must be unique")
        return tuple(sorted(normalized))
