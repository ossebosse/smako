"""Municipal selection over the existing prepared PriceUniverse manager."""
from dataclasses import replace
from math import asin, cos, radians, sin, sqrt

from grocery_data.app.domain.municipality import municipality_code
from grocery_data.app.services.municipal_rollout import refresh_scopes, scope_for_city


def configured_areas(settings):
    scopes = refresh_scopes()
    if not scopes:
        return [{"city": settings.price_universe_city,
                 "municipality_code": municipality_code(settings.price_universe_city),
                 "required_context_ids": list(settings.price_universe_required_context_ids)}]
    return scopes


def settings_for_city(settings, city):
    scope = scope_for_city(city)
    if scope is None:
        if city.casefold() != settings.price_universe_city.casefold():
            raise ValueError("municipality is not enabled")
        return settings
    return replace(settings, price_universe_city=scope["city"],
                   price_universe_required_context_ids=tuple(scope.get("required_context_ids", [])))


def required_contexts(settings, prepared):
    city = prepared.universe.key.scope_id.removeprefix("city:")
    scoped = settings_for_city(settings, city)
    if scoped.price_universe_required_context_ids:
        return set(scoped.price_universe_required_context_ids)
    if scope_for_city(city) is None:
        return set()
    # New scopes retain all published base catalogs as required, independently
    # of the selected personal basket and without borrowing Lund's context IDs.
    return {s.store_id for s in prepared.stores
            if s.source_provenance and s.source_provenance.source_channel == "catalog"}


def distance_to_store(store, latitude, longitude, *, precision=2):
    """Straight-line distance to verified coordinates; missing stays unknown."""
    if latitude is None or longitude is None:
        return None, None
    destinations = [(store.latitude, store.longitude, "store")]
    if store.price_context_type == "online_fulfillment":
        destinations = [(p.latitude, p.longitude, "pickup") for p in store.pickup_options]
    distances = []
    for lat, lon, basis in destinations:
        if lat is None or lon is None:
            continue
        a = sin(radians(lat - latitude) / 2) ** 2 + cos(radians(latitude)) * cos(radians(lat)) * sin(radians(lon - longitude) / 2) ** 2
        distance = 6371.0088 * 2 * asin(sqrt(min(1, max(0, a))))
        distances.append((round(distance, precision) if precision is not None else distance, basis))
    return min(distances) if distances else (None, None)
