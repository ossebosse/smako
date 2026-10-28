import gc
import weakref
from dataclasses import dataclass, fields, replace
from types import SimpleNamespace

import pytest
from app.services.basket_calculator import BasketItemQuote
from app.services.basket_optimizer import _QUOTE_LINE_SUFFIX, BasketOptimizer, _named_quote


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


def test_specialized_frozen_copy_retains_every_authoritative_field_and_future_defaults():
    # Distinct sentinels also populate optional fields: adding a new field must
    # fail this test unless the specialized copy explicitly preserves it.
    values = {field.name: object() for field in fields(BasketItemQuote)}
    original = BasketItemQuote(**values)
    changed = {'ingredient': 'current line', 'required_quantity': 115.5, 'waste_quantity': 384.5}
    copied = original.with_request(**changed)
    expected = replace(original, **changed)
    assert copied == expected and type(copied) is BasketItemQuote
    assert all(getattr(original, name) is value for name, value in values.items())
    assert all(getattr(copied, name) is value for name, value in values.items() if name not in changed)
    assert _named_quote(original, SimpleNamespace(canonical_name='current line')) == replace(
        original, ingredient='current line')
    with pytest.raises(AttributeError):
        copied.total_price = 0


@pytest.mark.parametrize('field', ['named', 'items', 'line_free_quote_sets', 'subset_memberships', 'vector_groups'])
def test_search_cannot_retain_old_quotes_through_unaccounted_side_caches(field):
    class RetainedQuote:
        pass

    optimizer = BasketOptimizer()
    with optimizer.quote_cache():
        session = optimizer._quote_cache_context.get()
        value = RetainedQuote()
        reference = weakref.ref(value)
        getattr(session, field).update(dict.fromkeys(range(32769), value))
        del value
        with optimizer.quote_cache(reuse_existing=True):
            gc.collect()
            assert reference() is None
            assert not getattr(session, field)


def test_session_exit_releases_new_quote_copies_even_when_the_session_is_still_referenced():
    optimizer = BasketOptimizer()
    with optimizer.quote_cache():
        session = optimizer._quote_cache_context.get()
        for field in ['named', 'items', 'line_free_quote_sets']:
            getattr(session, field)['one'] = object()
    assert all(not getattr(session, field) for field in ['named', 'items', 'line_free_quote_sets'])
