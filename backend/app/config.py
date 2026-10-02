"""Small environment based configuration layer for the PoC."""

from __future__ import annotations

import hmac
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Test and audit commands must be able to import the backend without loading
# repository credentials.  Keep this aligned with grocery_data's loader.
if os.getenv("PYTHON_DOTENV_DISABLED", "").strip().casefold() not in {
    "1",
    "true",
    "yes",
    "on",
}:
    load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on", "ja"}


def _csv(value: str | None, default: str) -> tuple[str, ...]:
    result = tuple(
        item.strip().casefold()
        for item in (value if value is not None else default).split(",")
        if item.strip()
    )
    if not result:
        raise ValueError("comma-separated setting must contain at least one value")
    return result


def _int_csv(value: str | None, default: str) -> tuple[int, ...]:
    return tuple(int(item) for item in _csv(value, default))


def _optional_int(value: str | None) -> int | None:
    normalized = (value or "").strip()
    return int(normalized) if normalized else None


@dataclass(frozen=True, slots=True)
class Settings:
    complete_recipes_enabled: bool = False
    app_env: str = "development"
    app_version: str = "0.1.0"
    build_id: str = "local"
    public_base_url: str | None = None
    secret_key: str | None = field(default=None, repr=False)
    beta_admin_token: str | None = field(default=None, repr=False)
    refresh_report_dir: Path = Path("reports/refresh")
    refresh_runner_status_path: Path = Path("reports/operations/refresh-runner-status.json")
    source_retry_status_path: Path = Path("reports/operations/source-retry-status.json")
    daily_refresh_schedule: str | None = None
    coop_retry_schedule: str | None = None
    planner_rate_limit_requests: int = 8
    planner_rate_limit_window_seconds: int = 60
    planner_max_concurrent_requests: int = 1
    planner_max_queued_requests: int = 4
    feedback_rate_limit_requests: int = 10
    feedback_rate_limit_window_seconds: int = 3600
    frontend_error_rate_limit_requests: int = 30
    frontend_error_rate_limit_window_seconds: int = 3600
    analytics_rate_limit_requests: int = 180
    analytics_rate_limit_window_seconds: int = 3600
    community_rate_limit_requests: int = 30
    community_rate_limit_window_seconds: int = 3600
    receipt_rate_limit_requests: int = 8
    receipt_rate_limit_window_seconds: int = 3600
    privacy_erasure_rate_limit_requests: int = 3
    privacy_erasure_rate_limit_window_seconds: int = 3600
    planner_network_rate_limit_requests: int = 40
    feedback_network_rate_limit_requests: int = 50
    frontend_error_network_rate_limit_requests: int = 150
    analytics_network_rate_limit_requests: int = 900
    community_network_rate_limit_requests: int = 150
    receipt_network_rate_limit_requests: int = 40
    privacy_erasure_network_rate_limit_requests: int = 20
    rate_limit_max_keys: int = 20_000
    price_provider: str = "auto"
    # Directly constructed Settings keep legacy behaviour for backwards-
    # compatible service tests. Normal application configuration defaults to
    # the optimized strategy in ``from_env`` below.
    meal_plan_strategy: str = "legacy"
    primat_api_key: str | None = field(default=None, repr=False)
    primat_base_url: str = "https://primat.nu/api/v3"
    own_grocery_base_url: str | None = None
    own_grocery_max_age_hours: float = 48.0
    own_grocery_include_offers_only: bool = False
    price_universe_required_context_ids: tuple[str, ...] = ()
    max_price_age_hours: float = 48.0
    price_age_warning_hours: float = 36.0
    price_universe_required: bool = False
    price_universe_cache_root: Path = Path("price_universes")
    price_universe_city: str = "Lund"
    plan_store_path: Path = Path("data/consumer_plans.sqlite3")
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
    # Candidate stabilization remains an explicit deployment rollout so old
    # clients that rely on their requested candidate count keep that contract.
    # The production environment and example deployment enable the verified
    # path after the immutable BEFORE/reference controls have been captured.
    stable_candidate_search_enabled: bool = False
    stable_candidate_base_count: int = 120
    stable_candidate_search_limit: int = 160
    allow_provider_fallback: bool = False
    own_sources_only: bool = False
    openai_api_key: str | None = field(default=None, repr=False)
    openai_model: str = "gpt-5.4-mini"
    allow_mock_fallback: bool = False
    allow_medium_semantic_matches: bool = False
    allow_estimated_quantities: bool = True
    allow_unknown_quantities: bool = False
    allow_unknown_sale_model: bool = False

    def __post_init__(self) -> None:
        if self.app_env not in {"development", "test", "production"}:
            raise ValueError("APP_ENV must be development, test or production")
        for name, value in (
            ("PLANNER_RATE_LIMIT_REQUESTS", self.planner_rate_limit_requests),
            ("PLANNER_RATE_LIMIT_WINDOW_SECONDS", self.planner_rate_limit_window_seconds),
            (
                "PLANNER_MAX_CONCURRENT_REQUESTS",
                self.planner_max_concurrent_requests,
            ),
            ("FEEDBACK_RATE_LIMIT_REQUESTS", self.feedback_rate_limit_requests),
            ("FEEDBACK_RATE_LIMIT_WINDOW_SECONDS", self.feedback_rate_limit_window_seconds),
            (
                "FRONTEND_ERROR_RATE_LIMIT_REQUESTS",
                self.frontend_error_rate_limit_requests,
            ),
            (
                "FRONTEND_ERROR_RATE_LIMIT_WINDOW_SECONDS",
                self.frontend_error_rate_limit_window_seconds,
            ),
            ("ANALYTICS_RATE_LIMIT_REQUESTS", self.analytics_rate_limit_requests),
            ("ANALYTICS_RATE_LIMIT_WINDOW_SECONDS", self.analytics_rate_limit_window_seconds),
            ("COMMUNITY_RATE_LIMIT_REQUESTS", self.community_rate_limit_requests),
            (
                "COMMUNITY_RATE_LIMIT_WINDOW_SECONDS",
                self.community_rate_limit_window_seconds,
            ),
            ("RECEIPT_RATE_LIMIT_REQUESTS", self.receipt_rate_limit_requests),
            (
                "RECEIPT_RATE_LIMIT_WINDOW_SECONDS",
                self.receipt_rate_limit_window_seconds,
            ),
            (
                "PRIVACY_ERASURE_RATE_LIMIT_REQUESTS",
                self.privacy_erasure_rate_limit_requests,
            ),
            (
                "PRIVACY_ERASURE_RATE_LIMIT_WINDOW_SECONDS",
                self.privacy_erasure_rate_limit_window_seconds,
            ),
            (
                "PLANNER_NETWORK_RATE_LIMIT_REQUESTS",
                self.planner_network_rate_limit_requests,
            ),
            (
                "FEEDBACK_NETWORK_RATE_LIMIT_REQUESTS",
                self.feedback_network_rate_limit_requests,
            ),
            (
                "FRONTEND_ERROR_NETWORK_RATE_LIMIT_REQUESTS",
                self.frontend_error_network_rate_limit_requests,
            ),
            (
                "ANALYTICS_NETWORK_RATE_LIMIT_REQUESTS",
                self.analytics_network_rate_limit_requests,
            ),
            (
                "COMMUNITY_NETWORK_RATE_LIMIT_REQUESTS",
                self.community_network_rate_limit_requests,
            ),
            (
                "RECEIPT_NETWORK_RATE_LIMIT_REQUESTS",
                self.receipt_network_rate_limit_requests,
            ),
            (
                "PRIVACY_ERASURE_NETWORK_RATE_LIMIT_REQUESTS",
                self.privacy_erasure_network_rate_limit_requests,
            ),
            ("RATE_LIMIT_MAX_KEYS", self.rate_limit_max_keys),
        ):
            if value < 1:
                raise ValueError(f"{name} must be at least one")
        if self.rate_limit_max_keys < 2:
            raise ValueError("RATE_LIMIT_MAX_KEYS must be at least two")
        if self.planner_max_queued_requests < 0:
            raise ValueError("PLANNER_MAX_QUEUED_REQUESTS must not be negative")
        for name, network_limit, session_limit in (
            (
                "PLANNER_NETWORK_RATE_LIMIT_REQUESTS",
                self.planner_network_rate_limit_requests,
                self.planner_rate_limit_requests,
            ),
            (
                "FEEDBACK_NETWORK_RATE_LIMIT_REQUESTS",
                self.feedback_network_rate_limit_requests,
                self.feedback_rate_limit_requests,
            ),
            (
                "FRONTEND_ERROR_NETWORK_RATE_LIMIT_REQUESTS",
                self.frontend_error_network_rate_limit_requests,
                self.frontend_error_rate_limit_requests,
            ),
            (
                "ANALYTICS_NETWORK_RATE_LIMIT_REQUESTS",
                self.analytics_network_rate_limit_requests,
                self.analytics_rate_limit_requests,
            ),
            (
                "COMMUNITY_NETWORK_RATE_LIMIT_REQUESTS",
                self.community_network_rate_limit_requests,
                self.community_rate_limit_requests,
            ),
            (
                "RECEIPT_NETWORK_RATE_LIMIT_REQUESTS",
                self.receipt_network_rate_limit_requests,
                self.receipt_rate_limit_requests,
            ),
            (
                "PRIVACY_ERASURE_NETWORK_RATE_LIMIT_REQUESTS",
                self.privacy_erasure_network_rate_limit_requests,
                self.privacy_erasure_rate_limit_requests,
            ),
        ):
            if network_limit <= session_limit:
                raise ValueError(f"{name} must be greater than its session limit")
        if self.app_env == "production":
            if self.public_base_url is None or not self.public_base_url.startswith("https://"):
                raise ValueError("PUBLIC_BASE_URL must use HTTPS in production")
            if (
                self.secret_key is None
                or len(self.secret_key.encode("utf-8")) < 32
                or self.secret_key.casefold().startswith(("replace-with", "change-me"))
            ):
                raise ValueError("SECRET_KEY must contain at least 32 bytes in production")
            if (
                self.beta_admin_token is None
                or len(self.beta_admin_token.encode("utf-8")) < 32
                or self.beta_admin_token.casefold().startswith(("replace-with", "change-me"))
            ):
                raise ValueError("BETA_ADMIN_TOKEN must contain at least 32 bytes in production")
            if hmac.compare_digest(self.secret_key, self.beta_admin_token):
                raise ValueError("SECRET_KEY and BETA_ADMIN_TOKEN must be different in production")
            if not re.fullmatch(
                r"\d+\.\d+\.\d+(?:-[0-9A-Za-z][0-9A-Za-z.-]*)?"
                r"(?:\+[0-9A-Za-z][0-9A-Za-z.-]*)?",
                self.app_version,
            ):
                raise ValueError("APP_VERSION must be an explicit semver-like release")
            normalized_build = self.build_id.strip()
            if (
                not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{5,127}", normalized_build)
                or normalized_build.casefold()
                in {
                    "local",
                    "unknown",
                    "default",
                    "development",
                }
                or normalized_build.casefold().startswith(("replace-with", "change-me"))
            ):
                raise ValueError("BUILD_ID must identify the deployed release")

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            complete_recipes_enabled=_as_bool(os.getenv("COMPLETE_RECIPES_ENABLED")),
            app_env=os.getenv("APP_ENV", "development").strip().casefold(),
            app_version=os.getenv("APP_VERSION", "0.1.0").strip() or "0.1.0",
            build_id=os.getenv("BUILD_ID", "local").strip() or "local",
            public_base_url=(os.getenv("PUBLIC_BASE_URL", "").strip() or None),
            secret_key=(os.getenv("SECRET_KEY", "").strip() or None),
            beta_admin_token=(os.getenv("BETA_ADMIN_TOKEN", "").strip() or None),
            refresh_report_dir=Path(os.getenv("REFRESH_REPORT_DIR", "reports/refresh")),
            refresh_runner_status_path=Path(
                os.getenv(
                    "REFRESH_RUNNER_STATUS_PATH",
                    "reports/operations/refresh-runner-status.json",
                )
            ),
            source_retry_status_path=Path(
                os.getenv(
                    "SOURCE_RETRY_STATUS_PATH",
                    "reports/operations/source-retry-status.json",
                )
            ),
            daily_refresh_schedule=(os.getenv("DAILY_REFRESH_SCHEDULE", "").strip() or None),
            coop_retry_schedule=(os.getenv("COOP_RETRY_SCHEDULE", "").strip() or None),
            planner_rate_limit_requests=int(os.getenv("PLANNER_RATE_LIMIT_REQUESTS", "8")),
            planner_rate_limit_window_seconds=int(
                os.getenv("PLANNER_RATE_LIMIT_WINDOW_SECONDS", "60")
            ),
            planner_max_concurrent_requests=int(os.getenv("PLANNER_MAX_CONCURRENT_REQUESTS", "1")),
            planner_max_queued_requests=int(os.getenv("PLANNER_MAX_QUEUED_REQUESTS", "4")),
            feedback_rate_limit_requests=int(os.getenv("FEEDBACK_RATE_LIMIT_REQUESTS", "10")),
            feedback_rate_limit_window_seconds=int(
                os.getenv("FEEDBACK_RATE_LIMIT_WINDOW_SECONDS", "3600")
            ),
            frontend_error_rate_limit_requests=int(
                os.getenv("FRONTEND_ERROR_RATE_LIMIT_REQUESTS", "30")
            ),
            frontend_error_rate_limit_window_seconds=int(
                os.getenv("FRONTEND_ERROR_RATE_LIMIT_WINDOW_SECONDS", "3600")
            ),
            analytics_rate_limit_requests=int(os.getenv("ANALYTICS_RATE_LIMIT_REQUESTS", "180")),
            analytics_rate_limit_window_seconds=int(
                os.getenv("ANALYTICS_RATE_LIMIT_WINDOW_SECONDS", "3600")
            ),
            community_rate_limit_requests=int(os.getenv("COMMUNITY_RATE_LIMIT_REQUESTS", "30")),
            community_rate_limit_window_seconds=int(
                os.getenv("COMMUNITY_RATE_LIMIT_WINDOW_SECONDS", "3600")
            ),
            receipt_rate_limit_requests=int(os.getenv("RECEIPT_RATE_LIMIT_REQUESTS", "8")),
            receipt_rate_limit_window_seconds=int(
                os.getenv("RECEIPT_RATE_LIMIT_WINDOW_SECONDS", "3600")
            ),
            privacy_erasure_rate_limit_requests=int(
                os.getenv("PRIVACY_ERASURE_RATE_LIMIT_REQUESTS", "3")
            ),
            privacy_erasure_rate_limit_window_seconds=int(
                os.getenv("PRIVACY_ERASURE_RATE_LIMIT_WINDOW_SECONDS", "3600")
            ),
            planner_network_rate_limit_requests=int(
                os.getenv("PLANNER_NETWORK_RATE_LIMIT_REQUESTS", "40")
            ),
            feedback_network_rate_limit_requests=int(
                os.getenv("FEEDBACK_NETWORK_RATE_LIMIT_REQUESTS", "50")
            ),
            frontend_error_network_rate_limit_requests=int(
                os.getenv("FRONTEND_ERROR_NETWORK_RATE_LIMIT_REQUESTS", "150")
            ),
            analytics_network_rate_limit_requests=int(
                os.getenv("ANALYTICS_NETWORK_RATE_LIMIT_REQUESTS", "900")
            ),
            community_network_rate_limit_requests=int(
                os.getenv("COMMUNITY_NETWORK_RATE_LIMIT_REQUESTS", "150")
            ),
            receipt_network_rate_limit_requests=int(
                os.getenv("RECEIPT_NETWORK_RATE_LIMIT_REQUESTS", "40")
            ),
            privacy_erasure_network_rate_limit_requests=int(
                os.getenv("PRIVACY_ERASURE_NETWORK_RATE_LIMIT_REQUESTS", "20")
            ),
            rate_limit_max_keys=int(os.getenv("RATE_LIMIT_MAX_KEYS", "20000")),
            price_provider=os.getenv("PRICE_PROVIDER", "auto").strip().lower(),
            meal_plan_strategy=os.getenv("MEAL_PLAN_STRATEGY", "optimized").strip().lower(),
            primat_api_key=os.getenv("PRIMAT_API_KEY") or None,
            primat_base_url=os.getenv("PRIMAT_BASE_URL", "https://primat.nu/api/v3").rstrip("/"),
            own_grocery_base_url=(os.getenv("OWN_GROCERY_BASE_URL") or "").rstrip("/") or None,
            own_grocery_max_age_hours=float(os.getenv("OWN_GROCERY_MAX_AGE_HOURS", "48")),
            own_grocery_include_offers_only=_as_bool(
                os.getenv("OWN_GROCERY_INCLUDE_OFFERS_ONLY"), False
            ),
            price_universe_required_context_ids=tuple(
                value.strip()
                for value in os.getenv("PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS", "").split(",")
                if value.strip()
            ),
            max_price_age_hours=float(os.getenv("MAX_PRICE_AGE_HOURS", "48")),
            price_age_warning_hours=float(os.getenv("PRICE_AGE_WARNING_HOURS", "36")),
            price_universe_required=_as_bool(
                os.getenv("PRICE_UNIVERSE_REQUIRED"),
                True,
            ),
            price_universe_cache_root=Path(
                os.getenv("PRICE_UNIVERSE_CACHE_ROOT", "price_universes")
            ),
            price_universe_city=os.getenv("PRICE_UNIVERSE_CITY", "Lund").strip() or "Lund",
            plan_store_path=Path(os.getenv("PLAN_STORE_PATH", "data/consumer_plans.sqlite3")),
            price_universe_prewarm_enabled=_as_bool(
                os.getenv("PRICE_UNIVERSE_PREWARM_ENABLED"),
                False,
            ),
            price_universe_prewarm_postal_code=os.getenv(
                "PRICE_UNIVERSE_PREWARM_POSTAL_CODE",
                "22350",
            ).strip(),
            price_universe_prewarm_modes=_csv(
                os.getenv("PRICE_UNIVERSE_PREWARM_MODES"),
                "cheapest,balanced,varied",
            ),
            price_universe_prewarm_max_stores=_int_csv(
                os.getenv("PRICE_UNIVERSE_PREWARM_MAX_STORES"),
                "1,2",
            ),
            price_universe_prewarm_recipes=int(os.getenv("PRICE_UNIVERSE_PREWARM_RECIPES", "5")),
            price_universe_prewarm_servings=int(os.getenv("PRICE_UNIVERSE_PREWARM_SERVINGS", "4")),
            price_universe_prewarm_candidate_count=int(
                os.getenv("PRICE_UNIVERSE_PREWARM_CANDIDATE_COUNT", "80")
            ),
            price_universe_prewarm_candidate_search_limit=_optional_int(
                os.getenv("PRICE_UNIVERSE_PREWARM_CANDIDATE_SEARCH_LIMIT")
            ),
            price_universe_prewarm_beam_width=int(
                os.getenv("PRICE_UNIVERSE_PREWARM_BEAM_WIDTH", "30")
            ),
            stable_candidate_search_enabled=_as_bool(
                os.getenv("STABLE_CANDIDATE_SEARCH_ENABLED"),
                False,
            ),
            stable_candidate_base_count=int(os.getenv("STABLE_CANDIDATE_BASE_COUNT", "120")),
            stable_candidate_search_limit=int(os.getenv("STABLE_CANDIDATE_SEARCH_LIMIT", "160")),
            allow_provider_fallback=_as_bool(
                os.getenv("ALLOW_PROVIDER_FALLBACK"),
                False,
            ),
            own_sources_only=_as_bool(os.getenv("OWN_SOURCES_ONLY"), False),
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini").strip(),
            # Live errors stay visible unless example-data fallback has been
            # explicitly opted into by the operator.
            allow_mock_fallback=_as_bool(os.getenv("ALLOW_MOCK_FALLBACK"), False),
            allow_medium_semantic_matches=_as_bool(
                os.getenv("ALLOW_MEDIUM_SEMANTIC_MATCHES"), False
            ),
            allow_estimated_quantities=_as_bool(os.getenv("ALLOW_ESTIMATED_QUANTITIES"), True),
            allow_unknown_quantities=_as_bool(os.getenv("ALLOW_UNKNOWN_QUANTITIES"), False),
            allow_unknown_sale_model=_as_bool(os.getenv("ALLOW_UNKNOWN_SALE_MODEL"), False),
        )


def get_settings() -> Settings:
    """Return fresh settings so tests can safely monkeypatch the environment."""

    return Settings.from_env()
