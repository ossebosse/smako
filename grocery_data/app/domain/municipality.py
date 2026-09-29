"""Official code/name register; no locality-to-municipality inference."""
import json
import unicodedata
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def municipality_register() -> dict:
    return json.loads((Path(__file__).parents[1] / "services/fixtures/scb_municipalities_2026.json").read_text(encoding="utf-8"))


def municipality_name(code: str) -> str:
    try:
        return municipality_register()["municipalities"][code]
    except KeyError as exc:
        raise ValueError("unknown official municipality code") from exc


def municipality_code(name: str) -> str | None:
    key = unicodedata.normalize("NFC", name).casefold().strip()
    return next((code for code, value in municipality_register()["municipalities"].items()
                 if unicodedata.normalize("NFC", value).casefold() == key), None)
