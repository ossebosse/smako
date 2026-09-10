from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _environment_flag(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError(f"{name} must be a boolean flag")


def _environment_csv(name: str, *, default: str) -> tuple[str, ...]:
    values = tuple(
        value.strip().casefold()
        for value in os.getenv(name, default).split(",")
        if value.strip()
    )
    if not values:
        raise ValueError(f"{name} must contain at least one value")
    return values


def _environment_int_csv(name: str, *, default: str) -> tuple[int, ...]:
    try:
        return tuple(int(value) for value in _environment_csv(name, default=default))
    except ValueError as exc:
        raise ValueError(f"{name} must contain comma-separated integers") from exc


def _environment_optional_int(name: str) -> int | None:
    value = os.getenv(name, "").strip()
    return int(value) if value else None


def _environment_optional_csv(name: str) -> tuple[str, ...]:
    return tuple(
        value.strip()
        for value in os.getenv(name, "").split(",")
        if value.strip()
    )


def load_repository_dotenv(dotenv_path: Path | None = None) -> bool:
    """Load the repository dotenv without overriding process configuration.

    Tests and credential-free commands can set ``PYTHON_DOTENV_DISABLED`` to
    guarantee that no dotenv file is opened.  Accepting a path keeps the loader
    testable without ever touching a developer's real ``.env``.
    """

    disabled = os.getenv("PYTHON_DOTENV_DISABLED", "").strip().casefold()
    if disabled in {"1", "true", "yes", "on"}:
        return False
    return load_dotenv(dotenv_path or REPOSITORY_ROOT / ".env", override=False)


@dataclass(frozen=True, slots=True)
class GroceryDataSettings:
    database_url: str
    raw_snapshot_root: Path
    user_agent: str
    ica_recipe_price_max_age_days: int = 7
    ica_max_page_navigations_per_run: int = 10
    ica_max_product_detail_pages_per_run: int = 5
    max_price_age_hours: float = 48.0
    price_age_warning_hours: float = 36.0
    min_sample_for_accuracy_score: int = 20
    field_validation_max_price_age_hours: float = 2.0
    current_offers_max_age_hours: float = 24.0
    community_evidence_max_reports_per_hour: int = 60
    community_evidence_duplicate_window_hours: float = 1.0
    community_availability_half_life_hours: float = 168.0
    community_evidence_recent_hours: float = 72.0
    community_receipt_raw_retention_hours: float = 0.0
    community_admin_token: str | None = field(default=None, repr=False)
    price_universe_cache_root: Path = Path("./price_universes")
    price_universe_prewarm_enabled: bool = False
    price_universe_prewarm_postal_code: str = "22350"
    price_universe_prewarm_modes: tuple[str, ...] = (
        "cheapest",
        "balanced",
        "varied",
    )
    price_universe_prewarm_max_stores: tuple[int, ...] = (1, 2)
    price_universe_prewarm_recipes: int = 5
    price_universe_prewarm_servings: int = 4
    price_universe_prewarm_candidate_count: int = 80
    price_universe_prewarm_candidate_search_limit: int | None = None
    price_universe_prewarm_beam_width: int = 30
    allow_provider_fallback: bool = False
    own_sources_only: bool = False
    field_mode_enabled: bool = False
    physical_check_access_token: str | None = field(default=None, repr=False)
    field_session_ttl_seconds: int = 3600
    field_login_attempts_per_minute: int = 5
    field_write_requests_per_minute: int = 60
    field_public_origin: str | None = None
    field_trusted_proxy_cidrs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.max_price_age_hours <= 0:
            raise ValueError("MAX_PRICE_AGE_HOURS must be greater than zero")
        if self.price_age_warning_hours <= 0:
            raise ValueError("PRICE_AGE_WARNING_HOURS must be greater than zero")
        if self.price_age_warning_hours >= self.max_price_age_hours:
            raise ValueError("PRICE_AGE_WARNING_HOURS must be below MAX_PRICE_AGE_HOURS")
        if self.min_sample_for_accuracy_score <= 0:
            raise ValueError("MIN_SAMPLE_FOR_ACCURACY_SCORE must be greater than zero")
        if self.field_validation_max_price_age_hours <= 0:
            raise ValueError(
                "FIELD_VALIDATION_MAX_PRICE_AGE_HOURS must be greater than zero"
            )
        if self.current_offers_max_age_hours <= 0:
            raise ValueError("CURRENT_OFFERS_MAX_AGE_HOURS must be greater than zero")
        if not 1 <= self.community_evidence_max_reports_per_hour <= 1000:
            raise ValueError(
                "COMMUNITY_EVIDENCE_MAX_REPORTS_PER_HOUR must be between 1 and 1000"
            )
        if self.community_evidence_duplicate_window_hours <= 0:
            raise ValueError(
                "COMMUNITY_EVIDENCE_DUPLICATE_WINDOW_HOURS must be greater than zero"
            )
        if self.community_availability_half_life_hours <= 0:
            raise ValueError(
                "COMMUNITY_AVAILABILITY_HALF_LIFE_HOURS must be greater than zero"
            )
        if self.community_evidence_recent_hours <= 0:
            raise ValueError("COMMUNITY_EVIDENCE_RECENT_HOURS must be greater than zero")
        if not 0 <= self.community_receipt_raw_retention_hours <= 24:
            raise ValueError(
                "COMMUNITY_RECEIPT_RAW_RETENTION_HOURS must be between 0 and 24"
            )
        if self.community_admin_token is not None and len(
            self.community_admin_token.encode("utf-8")
        ) < 32:
            raise ValueError("COMMUNITY_ADMIN_TOKEN must contain at least 32 bytes")
        if self.field_mode_enabled:
            token = self.physical_check_access_token or ""
            if len(token.encode("utf-8")) < 32:
                raise ValueError(
                    "PHYSICAL_CHECK_ACCESS_TOKEN must contain at least 32 bytes "
                    "when FIELD_MODE_ENABLED=true"
                )
        if not 60 <= self.field_session_ttl_seconds <= 3600:
            raise ValueError("FIELD_SESSION_TTL_SECONDS must be between 60 and 3600")
        if not 1 <= self.field_login_attempts_per_minute <= 100:
            raise ValueError("FIELD_LOGIN_ATTEMPTS_PER_MINUTE must be between 1 and 100")
        if not 1 <= self.field_write_requests_per_minute <= 600:
            raise ValueError("FIELD_WRITE_REQUESTS_PER_MINUTE must be between 1 and 600")
        from grocery_data.app.services.plan_prewarm import StandardPlanPrewarmConfig

        StandardPlanPrewarmConfig(
            enabled=self.price_universe_prewarm_enabled,
            postal_code=self.price_universe_prewarm_postal_code,
            modes=self.price_universe_prewarm_modes,
            max_stores=self.price_universe_prewarm_max_stores,
            recipes=self.price_universe_prewarm_recipes,
            servings=self.price_universe_prewarm_servings,
            candidate_recipe_count=self.price_universe_prewarm_candidate_count,
            candidate_search_limit=self.price_universe_prewarm_candidate_search_limit,
            beam_width=self.price_universe_prewarm_beam_width,
        )

    def standard_plan_prewarm_config(self):  # type: ignore[no-untyped-def]
        from grocery_data.app.services.plan_prewarm import StandardPlanPrewarmConfig

        return StandardPlanPrewarmConfig(
            enabled=self.price_universe_prewarm_enabled,
            postal_code=self.price_universe_prewarm_postal_code,
            modes=self.price_universe_prewarm_modes,
            max_stores=self.price_universe_prewarm_max_stores,
            recipes=self.price_universe_prewarm_recipes,
            servings=self.price_universe_prewarm_servings,
            candidate_recipe_count=self.price_universe_prewarm_candidate_count,
            candidate_search_limit=self.price_universe_prewarm_candidate_search_limit,
            beam_width=self.price_universe_prewarm_beam_width,
        )

    @classmethod
    def from_env(cls) -> GroceryDataSettings:
        # Secrets remain opaque values and this dataclass intentionally has no
        # custom debug logging. The database password must never be emitted.
        # Normal deployments should provide a PostgreSQL DSN. The credential-
        # free SQLite value is only a local PoC fallback; no username/password
        # is ever embedded in source.
        default_database = "sqlite+pysqlite:///./grocery_data.sqlite"
        return cls(
            database_url=os.getenv("GROCERY_DATABASE_URL", "").strip() or default_database,
            raw_snapshot_root=Path(os.getenv("GROCERY_RAW_SNAPSHOT_ROOT", "./raw_snapshots")),
            user_agent=os.getenv(
                "GROCERY_DATA_USER_AGENT",
                "grocery-data-poc/0.1 (+source-transparency)",
            ),
            ica_recipe_price_max_age_days=int(os.getenv("ICA_RECIPE_PRICE_MAX_AGE_DAYS", "7")),
            ica_max_page_navigations_per_run=int(
                os.getenv("ICA_MAX_PAGE_NAVIGATIONS_PER_RUN", "10")
            ),
            ica_max_product_detail_pages_per_run=int(
                os.getenv("ICA_MAX_PRODUCT_DETAIL_PAGES_PER_RUN", "5")
            ),
            max_price_age_hours=float(os.getenv("MAX_PRICE_AGE_HOURS", "48")),
            price_age_warning_hours=float(os.getenv("PRICE_AGE_WARNING_HOURS", "36")),
            min_sample_for_accuracy_score=int(
                os.getenv("MIN_SAMPLE_FOR_ACCURACY_SCORE", "20")
            ),
            field_validation_max_price_age_hours=float(
                os.getenv("FIELD_VALIDATION_MAX_PRICE_AGE_HOURS", "2")
            ),
            current_offers_max_age_hours=float(
                os.getenv("CURRENT_OFFERS_MAX_AGE_HOURS", "24")
            ),
            community_evidence_max_reports_per_hour=int(
                os.getenv("COMMUNITY_EVIDENCE_MAX_REPORTS_PER_HOUR", "60")
            ),
            community_evidence_duplicate_window_hours=float(
                os.getenv("COMMUNITY_EVIDENCE_DUPLICATE_WINDOW_HOURS", "1")
            ),
            community_availability_half_life_hours=float(
                os.getenv("COMMUNITY_AVAILABILITY_HALF_LIFE_HOURS", "168")
            ),
            community_evidence_recent_hours=float(
                os.getenv("COMMUNITY_EVIDENCE_RECENT_HOURS", "72")
            ),
            community_receipt_raw_retention_hours=float(
                os.getenv("COMMUNITY_RECEIPT_RAW_RETENTION_HOURS", "0")
            ),
            community_admin_token=(os.getenv("COMMUNITY_ADMIN_TOKEN", "").strip() or None),
            price_universe_cache_root=Path(
                os.getenv("PRICE_UNIVERSE_CACHE_ROOT", "./price_universes")
            ),
            price_universe_prewarm_enabled=_environment_flag(
                "PRICE_UNIVERSE_PREWARM_ENABLED",
                default=False,
            ),
            price_universe_prewarm_postal_code=os.getenv(
                "PRICE_UNIVERSE_PREWARM_POSTAL_CODE",
                "22350",
            ).strip(),
            price_universe_prewarm_modes=_environment_csv(
                "PRICE_UNIVERSE_PREWARM_MODES",
                default="cheapest,balanced,varied",
            ),
            price_universe_prewarm_max_stores=_environment_int_csv(
                "PRICE_UNIVERSE_PREWARM_MAX_STORES",
                default="1,2",
            ),
            price_universe_prewarm_recipes=int(
                os.getenv("PRICE_UNIVERSE_PREWARM_RECIPES", "5")
            ),
            price_universe_prewarm_servings=int(
                os.getenv("PRICE_UNIVERSE_PREWARM_SERVINGS", "4")
            ),
            price_universe_prewarm_candidate_count=int(
                os.getenv("PRICE_UNIVERSE_PREWARM_CANDIDATE_COUNT", "80")
            ),
            price_universe_prewarm_candidate_search_limit=_environment_optional_int(
                "PRICE_UNIVERSE_PREWARM_CANDIDATE_SEARCH_LIMIT"
            ),
            price_universe_prewarm_beam_width=int(
                os.getenv("PRICE_UNIVERSE_PREWARM_BEAM_WIDTH", "30")
            ),
            allow_provider_fallback=_environment_flag(
                "ALLOW_PROVIDER_FALLBACK",
                default=False,
            ),
            own_sources_only=_environment_flag("OWN_SOURCES_ONLY", default=False),
            field_mode_enabled=_environment_flag("FIELD_MODE_ENABLED", default=False),
            physical_check_access_token=(
                os.getenv("PHYSICAL_CHECK_ACCESS_TOKEN", "").strip() or None
            ),
            field_session_ttl_seconds=int(
                os.getenv("FIELD_SESSION_TTL_SECONDS", "3600")
            ),
            field_login_attempts_per_minute=int(
                os.getenv("FIELD_LOGIN_ATTEMPTS_PER_MINUTE", "5")
            ),
            field_write_requests_per_minute=int(
                os.getenv("FIELD_WRITE_REQUESTS_PER_MINUTE", "60")
            ),
            field_public_origin=(
                os.getenv("FIELD_PUBLIC_ORIGIN", "").strip() or None
            ),
            field_trusted_proxy_cidrs=_environment_optional_csv(
                "FIELD_TRUSTED_PROXY_CIDRS"
            ),
        )
