"""Explicit historical replay clock. Never imported by application code."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def install_clock():
    from app.services import (
        meal_plan_optimizer,
        personal_planner,
        price_universe_runtime,
        user_pricing,
    )
    clock = datetime.fromisoformat(json.loads(Path('/inputs/freeze.json').read_text())['frozen_at_utc'])

    class ReplayClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.astimezone(tz) if tz else clock.replace(tzinfo=None)

    for module in (meal_plan_optimizer, personal_planner, price_universe_runtime):
        module.datetime = ReplayClock
    meal_plan_optimizer.current_pricing_date = user_pricing.current_pricing_date = lambda: clock.astimezone(ZoneInfo('Europe/Stockholm')).date()
    return clock
