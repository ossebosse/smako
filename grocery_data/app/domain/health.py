from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from grocery_data.app.domain.enums import Chain, ConnectorStatus, CoverageLevel


class RunMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    stores_found: int = Field(default=0, ge=0)
    stores_successful: int = Field(default=0, ge=0)
    stores_failed: int = Field(default=0, ge=0)
    products_fetched: int = Field(default=0, ge=0)
    products_parsed: int = Field(default=0, ge=0)
    products_quarantined: int = Field(default=0, ge=0)
    products_with_price: int = Field(default=0, ge=0)
    products_with_gtin: int = Field(default=0, ge=0)
    products_with_package_quantity: int = Field(default=0, ge=0)
    unknown_sale_model: int = Field(default=0, ge=0)
    request_count: int = Field(default=0, ge=0)
    http_error_count: int = Field(default=0, ge=0)
    rate_limit_count: int = Field(default=0, ge=0)
    runtime_ms: int = Field(default=0, ge=0)

    @property
    def parse_success_rate(self) -> float:
        denominator = self.products_parsed + self.products_quarantined
        return self.products_parsed / denominator if denominator else 0.0

    @property
    def price_coverage(self) -> float:
        return self.products_with_price / self.products_parsed if self.products_parsed else 0.0

    @property
    def gtin_coverage(self) -> float:
        return self.products_with_gtin / self.products_parsed if self.products_parsed else 0.0

    @property
    def package_coverage(self) -> float:
        if not self.products_parsed:
            return 0.0
        return self.products_with_package_quantity / self.products_parsed

    @property
    def unknown_sale_model_rate(self) -> float:
        return self.unknown_sale_model / self.products_parsed if self.products_parsed else 0.0


class ConnectorHealth(BaseModel):
    model_config = ConfigDict(frozen=True)

    chain: Chain
    coverage: CoverageLevel
    status: ConnectorStatus
    last_success_at: datetime | None = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    active_snapshot_id: str | None = None
    metrics: RunMetrics
    warnings: tuple[str, ...] = ()
    schema_fingerprint: str | None = None
