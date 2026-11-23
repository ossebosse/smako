from datetime import timedelta

from grocery_data.app.services.freshness import (
    FreshnessPolicy,
    price_max_age,
    price_max_age_hours,
    price_warning_age_hours,
)


def test_default_stays_48_hours(monkeypatch):
    monkeypatch.delenv("MAX_PRICE_AGE_HOURS", raising=False)
    monkeypatch.delenv("PRICE_AGE_WARNING_HOURS", raising=False)
    assert price_max_age() == timedelta(hours=48)
    assert FreshnessPolicy().stale_age_hours == 48 and FreshnessPolicy().warning_age_hours == 36


def test_one_setting_raises_the_limit_for_every_chain(monkeypatch):
    monkeypatch.setenv("MAX_PRICE_AGE_HOURS", "336")
    monkeypatch.setenv("PRICE_AGE_WARNING_HOURS", "240")
    assert price_max_age() == timedelta(days=14)
    assert FreshnessPolicy().stale_age_hours == 336 and FreshnessPolicy().warning_age_hours == 240


def test_bad_values_fall_back_safely(monkeypatch):
    monkeypatch.setenv("MAX_PRICE_AGE_HOURS", "nonsense")
    assert price_max_age_hours() == 48
    monkeypatch.setenv("MAX_PRICE_AGE_HOURS", "336")
    monkeypatch.setenv("PRICE_AGE_WARNING_HOURS", "400")
    assert price_warning_age_hours() == 252
