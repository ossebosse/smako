"""Fail-closed production policy for the one verified Coop online context.

The connector continues to own transport and source-policy enforcement.  This
small module only makes the deployment contract explicit and reusable by the
cron bootstrap, the full refresh wrapper and the bounded recovery job.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

COOP_VERIFIED_ONLINE_CONTEXT_ID = "730400"


class CoopRefreshConfigurationError(RuntimeError):
    """The production scheduler cannot safely refresh Coop Online Syd."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class CoopRefreshConfiguration:
    context_id: str
    configured_policy: str
    operator_opt_in: bool
    configured_context_ids: tuple[str, ...]
    valid: bool
    diagnostic_code: str | None

    def sanitized_report(self) -> dict[str, object]:
        """Return only non-secret policy facts suitable for operational logs."""

        return {
            "context_id": self.context_id,
            "required_context_id": self.context_id,
            "configured_policy": self.configured_policy,
            "operator_opt_in": self.operator_opt_in,
            "configured_context_ids": list(self.configured_context_ids),
            "configuration_valid": self.valid,
            "valid": self.valid,
            "diagnostic_code": self.diagnostic_code,
            "scope": "online_fulfillment",
            "price_semantics": "online_price",
        }


def _flag(value: str | None) -> bool | None:
    normalized = (value or "").strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"", "0", "false", "no", "off"}:
        return False
    return None


def assess_coop_refresh_configuration(
    environment: Mapping[str, str],
) -> CoopRefreshConfiguration:
    """Assess the exact shared scheduler/application Coop policy.

    Only ``730400`` is currently verified.  Additional identifiers fail the
    production preflight rather than silently broadening the crawl boundary.
    """

    raw_flag = _flag(environment.get("COOP_ALLOW_FULL_CRAWL"))
    context_ids = tuple(
        sorted(
            {
                value.strip()
                for value in environment.get("COOP_ONLINE_CONTEXT_IDS", "").split(",")
                if value.strip()
            }
        )
    )
    if raw_flag is None:
        code = "coop_full_catalog_opt_in_invalid"
    elif not raw_flag:
        code = "coop_full_catalog_disabled"
    elif COOP_VERIFIED_ONLINE_CONTEXT_ID not in context_ids:
        code = "coop_online_context_not_allowlisted"
    elif context_ids != (COOP_VERIFIED_ONLINE_CONTEXT_ID,):
        code = "coop_online_context_allowlist_too_broad"
    else:
        code = None
    return CoopRefreshConfiguration(
        context_id=COOP_VERIFIED_ONLINE_CONTEXT_ID,
        configured_policy="review",
        operator_opt_in=raw_flag is True,
        configured_context_ids=context_ids,
        valid=code is None,
        diagnostic_code=code,
    )


def require_coop_refresh_configuration(
    environment: Mapping[str, str],
) -> CoopRefreshConfiguration:
    assessment = assess_coop_refresh_configuration(environment)
    if not assessment.valid:
        raise CoopRefreshConfigurationError(
            assessment.diagnostic_code or "coop_refresh_configuration_invalid"
        )
    return assessment


__all__ = [
    "COOP_VERIFIED_ONLINE_CONTEXT_ID",
    "CoopRefreshConfiguration",
    "CoopRefreshConfigurationError",
    "assess_coop_refresh_configuration",
    "require_coop_refresh_configuration",
]
