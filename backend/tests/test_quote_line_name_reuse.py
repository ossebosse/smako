import gc
import weakref
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
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
