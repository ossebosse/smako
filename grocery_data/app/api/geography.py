from __future__ import annotations

from dataclasses import asdict, dataclass

SUPPORTED_POSTAL_PREFIXES = {
    "20": "Malmö",
    "21": "Malmö",
    "22": "Lund",
}

POSTAL_SCOPE_LIMITATION = (
    "PoC postal resolution is limited to the coarse Lund (22xxx) and Malmö (20xxx/21xxx) scopes."
)


@dataclass(frozen=True, slots=True)
class GeographicResolution:
    requested_postal_code: str
    normalized_postal_code: str
    resolved_city: str | None
    resolution: str
    coverage_limitation: str

    def as_dict(self) -> dict[str, str | None]:
        return asdict(self)


def resolve_postal_scope(postal_code: str) -> GeographicResolution:
    normalized = "".join(postal_code.split())
    if len(normalized) != 5 or not normalized.isdigit():
        return GeographicResolution(
            requested_postal_code=postal_code,
            normalized_postal_code=normalized,
            resolved_city=None,
            resolution="invalid",
            coverage_limitation=POSTAL_SCOPE_LIMITATION,
        )
    city = SUPPORTED_POSTAL_PREFIXES.get(normalized[:2])
    return GeographicResolution(
        requested_postal_code=postal_code,
        normalized_postal_code=normalized,
        resolved_city=city,
        resolution="postal_prefix" if city is not None else "unsupported",
        coverage_limitation=POSTAL_SCOPE_LIMITATION,
    )
