from dataclasses import dataclass
from types import SimpleNamespace

from app.services.basket_optimizer import _QUOTE_LINE_SUFFIX, _named_quote


@dataclass(frozen=True, slots=True)
class _Quote:
    ingredient: str
    total: float


def test_purchase_line_number_is_not_part_of_the_quote_identity():
    assert _QUOTE_LINE_SUFFIX.sub("", "basilika [13]") == "basilika"
    assert _QUOTE_LINE_SUFFIX.sub("", "basilika [2]") == _QUOTE_LINE_SUFFIX.sub("", "basilika [13]")
    assert _QUOTE_LINE_SUFFIX.sub("", "tomater [krossade]") == "tomater [krossade]"


def test_reused_quote_carries_the_current_line_name_and_nothing_else_changes():
    cached = _Quote("basilika [13]", 17.5)
    reused = _named_quote(cached, SimpleNamespace(canonical_name="basilika [2]"))
    assert reused == _Quote("basilika [2]", 17.5)
    assert _named_quote(cached, SimpleNamespace(canonical_name="basilika [13]")) is cached
