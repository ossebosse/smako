"""Replay an unchanged historical Willys test at its own observation date.

No source file, stored price observation or runtime clock is modified. The
test's current-clock call otherwise makes its expired member campaign inactive.
"""
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]
import app.models.product as product_module  # noqa: E402
import pytest  # noqa: E402


class FixtureClock(datetime):
    @classmethod
    def now(cls, tz=None):
        when = datetime(2026, 9, 19, 10, tzinfo=UTC)
        return when.astimezone(tz) if tz else when.replace(tzinfo=None)


product_module.datetime = FixtureClock
raise SystemExit(pytest.main([
    "-q", str(ROOT / "backend/tests/test_price_universe.py")
    + "::test_retained_public_catalog_price_equal_to_member_price_does_not_stop_build",
    "--junitxml=" + str(Path(__file__).with_name("tests-historical-replay.xml")),
]))
