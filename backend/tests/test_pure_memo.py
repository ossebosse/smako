"""pure_memo: lru_cache's answers and interface, without a lock on hits."""
import threading

import pytest
from app.services.pure_memo import pure_memo


def test_same_answers_bounded_and_errors_not_cached():
    calls = []

    @pure_memo(3)
    def square(x):
        calls.append(x)
        if x < 0:
            raise ValueError(x)
        return x * x

    assert [square(2), square(2), square(3)] == [4, 4, 9] and calls == [2, 3]
    assert square.cache_info() == (1, 2, 3, 2)
    for x in range(10):
        square(x)
    assert square.cache_info().currsize == 3
    with pytest.raises(ValueError):
        square(-1)
    with pytest.raises(ValueError):
        square(-1)
    assert calls.count(-1) == 2 and square.__wrapped__(5) == 25
    square.cache_clear()
    assert square.cache_info() == (0, 0, 3, 0)


def test_threads_get_the_same_answers():
    @pure_memo(64)
    def text(x):
        return f"v{x}"

    results = []

    def run():
        results.append([text(i % 100) for i in range(5000)])

    threads = [threading.Thread(target=run) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert all(r == [f"v{i % 100}" for i in range(5000)] for r in results)
    assert text.cache_info().currsize <= 64
