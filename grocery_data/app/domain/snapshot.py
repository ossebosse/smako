from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from grocery_data.app.domain.enums import Chain, SnapshotState


class StoredRawDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    document_id: str
    chain: Chain
    store_external_id: str | None = None
    kind: str
    method: str
    url: str
    query: dict[str, str] = Field(default_factory=dict)
    relative_path: str
    payload_hash: str
    fetched_at: datetime
    http_status: int
    content_type: str | None = None
    connector_version: str
    page_number: int | None = None
    schema_fingerprint: str | None = None

    def resolve(self, root: Path) -> Path:
        candidate = (root / self.relative_path).resolve()
        if root.resolve() not in candidate.parents:
            raise ValueError("raw document path escapes configured root")
        return candidate


class CatalogSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    snapshot_id: str
    chain: Chain
    store_external_id: str
    state: SnapshotState = SnapshotState.FETCHED
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    promoted_at: datetime | None = None
    parser_version: str
    normalizer_version: str
    product_count: int = Field(default=0, ge=0)
    is_active: bool = False
