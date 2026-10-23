"""Historical authority must survive sharing the current scaled registry."""

import pytest
from app.services import recipe_library as library


def test_history_reuses_current_portions_but_retains_distinct_issued_content(monkeypatch):
    source = library._registered()[0]
    current = library._scaled(source, 4)
    # A distinct source with the same claimed version must never borrow current
    # content. The issued index must still detect that conflicting publication.
    conflicting = source.model_copy(update={"name": source.name + " changed"})
    monkeypatch.setattr(library, "_registered", lambda: (source,))
    monkeypatch.setattr(library, "_registered_portions", lambda servings: (current,))
    monkeypatch.setattr(library, "_registered_history", lambda: (source, conflicting))
    # Isolate just structural validation to reach the index's independent
    # conflicting-publication check; normal structural validation rejects it too.
    monkeypatch.setattr(library, "_structural_check", lambda recipe: None)
    library._registered_historical_portions.cache_clear()
    library._issued_index.cache_clear()
    try:
        rows = library._registered_historical_portions(4)
        assert rows[0] is current
        assert rows[1].name == conflicting.name
        with pytest.raises(ValueError, match="Motstridigt innehåll"):
            library._issued_index(4)
    finally:
        library._registered_historical_portions.cache_clear()
        library._issued_index.cache_clear()


def test_shared_current_portions_still_receive_structural_validation(monkeypatch):
    source = library._registered()[0]
    damaged = library._scaled(source, 4)
    damaged.instructions.append("An unapproved mutable list edit")
    monkeypatch.setattr(library, "_registered", lambda: (source,))
    monkeypatch.setattr(library, "_registered_portions", lambda servings: (damaged,))
    monkeypatch.setattr(library, "_registered_history", lambda: (source,))
    library._registered_historical_portions.cache_clear()
    try:
        with pytest.raises(ValueError, match="Visade instruktioner"):
            library._registered_historical_portions(4)
    finally:
        library._registered_historical_portions.cache_clear()
