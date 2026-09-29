from __future__ import annotations

import json
from math import isfinite
from typing import Any


class IcaSchemaError(ValueError):
    pass


def initial_data_from_html(payload: bytes) -> dict[str, Any]:
    """Decode ICA's public ``window.__INITIAL_DATA__`` JavaScript literal.

    The source is JSON-shaped but currently contains bare ``undefined`` and
    ``new Map([])`` values.  Replacement is deliberately lexical and occurs
    only outside quoted strings; arbitrary JavaScript is never evaluated.
    """

    text = payload.decode("utf-8")
    stripped = text.lstrip()
    if stripped.startswith("{"):
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise IcaSchemaError("ICA sanitized initial data is not valid JSON") from exc
        if not isinstance(decoded, dict):
            raise IcaSchemaError("ICA initial data must be an object")
        return decoded
    marker = "window.__INITIAL_DATA__ ="
    start = text.find(marker)
    if start < 0:
        raise IcaSchemaError("ICA page is missing window.__INITIAL_DATA__")
    start += len(marker)
    end = text.find(";</script>", start)
    if end < 0:
        end = text.find("</script>", start)
    if end < 0:
        raise IcaSchemaError("ICA initial-data script is unterminated")
    literal = text[start:end].strip().removesuffix(";")
    literal = _replace_bare_javascript_values(literal)
    try:
        decoded = json.loads(literal)
    except json.JSONDecodeError as exc:
        raise IcaSchemaError("ICA initial-data literal is not supported JSON") from exc
    if not isinstance(decoded, dict):
        raise IcaSchemaError("ICA initial data must be an object")
    return decoded


def _scalar(value: object) -> str | int | float | bool | None:
    if value is None or isinstance(value, str | int | bool):
        return value
    if isinstance(value, float) and isfinite(value):
        return value
    return None


def _first_dict(value: object) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return next((item for item in value if isinstance(item, dict)), {})
    return {}


def _fields(row: dict[str, Any], names: tuple[str, ...]) -> dict[str, object]:
    return {name: _scalar(row[name]) for name in names if name in row}


def _sanitized_store_card(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    result = _fields(
        value,
        ("accountNumber", "storeId", "storeName", "name", "onlineUrl", "profile", "bhsUrl"),
    )
    address = _first_dict(value.get("address"))
    clean_address = _fields(
        address,
        ("street", "address", "postalCode", "city", "municipality"),
    )
    coordinates = _first_dict(address.get("coordinates") or value.get("coordinates")
                              or value.get("geoPosition"))
    clean_coordinates = _fields(
        coordinates,
        ("latitude", "longitude", "lat", "lng", "coordinateX", "coordinateY"),
    )
    if clean_coordinates:
        clean_address["coordinates"] = clean_coordinates
    if clean_address:
        result["address"] = clean_address

    offers = _first_dict(value.get("highlightUrls")).get("offers")
    if isinstance(offers, dict):
        clean_offer = _fields(offers, ("url",))
        if clean_offer:
            result["highlightUrls"] = {"offers": clean_offer}
    elif _scalar(offers) is not None:
        result["highlightUrls"] = {"offers": _scalar(offers)}
    return result


def _sanitized_offer(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    result = _fields(
        value,
        ("id", "validFrom", "validTo", "comparisonPrice", "restriction", "condition"),
    )
    nested_fields = {
        "details": ("name", "brand", "packageInformation", "mechanicInfo",
                    "customerInformation", "disclaimer"),
        "parsedMechanics": (
            "benefitType",
            "type",
            "quantity",
            "value1",
            "value2",
            "value3",
            "value4",
            "unitSign",
        ),
        "category": ("articleGroupName",),
    }
    for output_name, names in nested_fields.items():
        cleaned = _fields(_first_dict(value.get(output_name)), names)
        if cleaned:
            result[output_name] = cleaned

    stores: list[dict[str, object]] = []
    for store in value.get("stores") if isinstance(value.get("stores"), list) else ():
        if isinstance(store, dict):
            stores.append(
                _fields(
                    store,
                    ("BMSStoreId", "accountNumber", "regularPrice", "referencePriceText",
                     "storeInd", "onlineInd", "ecomDisclaimer"),
                )
            )
    result["stores"] = stores

    eans: list[dict[str, object]] = []
    for ean in value.get("eans") if isinstance(value.get("eans"), list) else ():
        eans.append(_fields(ean, ("id",)) if isinstance(ean, dict) else {})
    result["eans"] = eans

    traits: list[object] = []
    for trait in value.get("traits") if isinstance(value.get("traits"), list) else ():
        if isinstance(trait, dict):
            traits.append(_fields(trait, ("name",)))
        elif (cleaned_trait := _scalar(trait)) is not None:
            traits.append(cleaned_trait)
    result["traits"] = traits
    return result


def sanitized_initial_data_payload(payload: bytes, *, kind: str) -> bytes:
    """Return only public SSR fields required for ICA store/offer replay.

    Runtime configuration, browser/session state and arbitrary page scripts are
    excluded structurally before a :class:`RawFetch` can exist.
    """

    from .public_material import public_links

    if kind == "public_page":
        return json.dumps(public_links(payload), ensure_ascii=False).encode()
    data = initial_data_from_html(payload)
    if kind == "stores_page":
        source = _first_dict(data.get("resultStore"))
        cards = source.get("storeCards")
        if not isinstance(cards, list):
            raise IcaSchemaError("ICA storeCards must be a list")
        result: dict[str, object] = _fields(
            source,
            ("totalNrOfStores", "totalNumberOfStores", "total"),
        )
        result["storeCards"] = [
            card for value in cards if (card := _sanitized_store_card(value)) is not None
        ]
        # ICA publishes the whole current result in its map projection even
        # when the rendered list is paginated (20/69 in the Malmö verification).
        # Join by official account ID, never by ordering or display name.
        slim = _first_dict(data.get("SlimStores")).get("slimStores")
        if isinstance(slim, list):
            merged = {str(c.get("accountNumber")): c for v in slim
                      if (c := _sanitized_store_card(v)) and c.get("accountNumber")}
            for card in result["storeCards"]:
                key = str(card.get("accountNumber"))
                merged[key] = {**merged.get(key, {}), **card}
            if len(merged) > len(result["storeCards"]):
                result["renderedCardCount"] = len(cards)
                result["inventoryProjection"] = "official_slim_store_map_plus_visible_cards"
                result["storeCards"] = list(merged.values())
        sanitized: dict[str, object] = {
            "schema": "ica-public-ssr-v1",
            "resultStore": result,
        }
    elif kind == "offers_page":
        source = _first_dict(data.get("offers"))
        row_field = next(
            (
                name
                for name in ("weeklyOffers", "weeklyDeals")
                if isinstance(source.get(name), list)
            ),
            None,
        )
        if row_field is None:
            raise IcaSchemaError("ICA weeklyOffers must be a list")
        sanitized = {
            "schema": "ica-public-ssr-v1",
            "offers": {
                row_field: [
                    row
                    for value in source[row_field]
                    if (row := _sanitized_offer(value)) is not None
                ]
            },
        }
    else:
        raise IcaSchemaError(f"ICA raw kind is not sanitizable: {kind}")
    links = (data.get("public_links", {}) if payload.lstrip().startswith(b"{")
             else public_links(payload))
    sanitized["public_links"] = links
    return json.dumps(sanitized, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def _replace_bare_javascript_values(value: str) -> str:
    output: list[str] = []
    index = 0
    quote: str | None = None
    escaped = False
    replacements = {"undefined": "null", "new Map([])": "{}"}
    while index < len(value):
        char = value[index]
        if quote is not None:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
            output.append(char)
            index += 1
            continue
        replaced = False
        for token, replacement in replacements.items():
            if value.startswith(token, index):
                output.append(replacement)
                index += len(token)
                replaced = True
                break
        if not replaced:
            output.append(char)
            index += 1
    if quote is not None:
        raise IcaSchemaError("ICA initial-data literal contains an unterminated string")
    return "".join(output)
