"""Regression coverage for ICA's delayed Monday campaign publication."""
import unittest
from datetime import datetime, timedelta

from grocery_data.app.services import campaign_refresh_policy as policy


class CampaignScheduleTests(unittest.TestCase):
    def schedule(self, now, ends, **kwargs):
        return policy.campaign_schedule(
            [{'valid_to': end} for end in ends], now=datetime.fromisoformat(now), **kwargs)

    def test_soder_actual_monday_rollover_with_surviving_campaigns(self):
        now = '2026-10-11T22:15:39+00:00'
        result = self.schedule(now, ['2026-10-11'] * 55 + ['2026-10-18', '2026-11-01'])
        self.assertEqual(result['next_fetch_at'], '2026-10-11T23:15:39+00:00')
        self.assertEqual(result['reason'], 'campaign_rollover_retry')

    def test_all_expired_also_rechecks_in_one_hour(self):
        result = self.schedule('2026-10-11T22:15:00+00:00', ['2026-10-11'])
        self.assertEqual(result['next_fetch_at'], '2026-10-11T23:15:00+00:00')

    def test_current_week_still_uses_normal_72_hour_cap(self):
        result = self.schedule('2026-10-12T08:00:00+00:00', ['2026-10-18'])
        self.assertEqual(result['next_fetch_at'], '2026-10-15T08:00:00+00:00')

    def test_old_history_does_not_cause_permanent_hourly_polling(self):
        result = self.schedule('2026-10-14T08:00:00+00:00', ['2026-10-11', '2026-11-01'])
        self.assertEqual(result['next_fetch_at'], '2026-10-14T20:00:00+00:00')

    def test_failed_requests_preserve_backoff(self):
        now = '2026-10-11T22:15:00+00:00'
        for failures, minutes in [(1, 15), (4, 120), (20, 360)]:
            with self.subTest(failures=failures):
                result = self.schedule(now, ['2026-10-11', '2026-11-01'], failed_attempts=failures)
                self.assertEqual(datetime.fromisoformat(result['next_fetch_at']),
                                 datetime.fromisoformat(now) + timedelta(minutes=minutes))
                self.assertEqual(result['reason'], 'bounded_failure_retry')

    def test_exact_midnight_is_expired(self):
        result = self.schedule('2026-10-11T22:00:00+00:00', ['2026-10-11', '2026-11-01'])
        self.assertEqual(result['next_fetch_at'], '2026-10-11T23:00:00+00:00')

    def test_dst_uses_stockholm_midnight(self):
        result = self.schedule('2026-10-25T23:15:00+00:00', ['2026-10-25', '2026-11-01'])
        self.assertEqual(result['next_fetch_at'], '2026-10-26T00:15:00+00:00')

    def test_sooner_future_boundary_is_preserved(self):
        windows = [{'valid_to': '2026-10-11'}, {'valid_from': '2026-10-13', 'valid_to': '2026-10-18'}]
        result = policy.campaign_schedule(windows, now=datetime.fromisoformat('2026-10-12T21:50:00+00:00'))
        self.assertEqual(result['next_fetch_at'], '2026-10-12T22:15:00+00:00')

    def test_empty_and_unbounded_fallback_unchanged(self):
        for ends in ([], [None]):
            result = self.schedule('2026-10-14T08:00:00+00:00', ends)
            self.assertEqual(result['next_fetch_at'], '2026-10-14T20:00:00+00:00')

    def test_windows_are_not_rewritten(self):
        windows = [{'valid_to': '2026-10-11'}, {'valid_to': '2026-11-01'}]
        before = [dict(row) for row in windows]
        policy.campaign_schedule(windows, now=datetime.fromisoformat('2026-10-11T22:15:00+00:00'))
        self.assertEqual(windows, before)

    def test_naive_clock_is_rejected(self):
        with self.assertRaises(ValueError):
            policy.campaign_schedule([], now=datetime(2026, 10, 12))  # noqa: DTZ001


if __name__ == '__main__':
    unittest.main()
