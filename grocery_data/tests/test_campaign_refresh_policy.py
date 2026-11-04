from datetime import UTC, date, datetime, timedelta

import pytest

from grocery_data.app.domain.campaign_validity import CampaignEvidence
from grocery_data.app.services.campaign_refresh_policy import base_fetch_due, campaign_schedule

NOW = datetime(2026, 9, 20, 8, tzinfo=UTC)


def test_missing_start_is_observation_evidence_not_invented_monday():
    proof = CampaignEvidence(store_external_id='official', offer_id='offer', source_reference='raw:sha',
        observed_current_at=NOW, checked_at=NOW)
    assert not proof.applies(date(2026,9,19),None,date(2026,9,20))
    assert proof.applies(date(2026,9,20),None,date(2026,9,20))
    assert not proof.applies(date(2026,9,21),None,date(2026,9,20))
    assert not proof.applies(date(2026,9,20),date(2026,9,21),date(2026,9,27))
    assert not proof.applies(date(2026,9,20),None,None)


def test_sunday_campaign_preparation_and_transition_use_stockholm_midnight():
    schedule = campaign_schedule([{'valid_from':None,'valid_to':'2026-09-20'}],now=NOW)
    assert datetime.fromisoformat(schedule['next_fetch_at']) == datetime(2026,9,20,21,tzinfo=UTC)
    assert datetime.fromisoformat(schedule['next_transition_at']) == datetime(2026,9,20,22,tzinfo=UTC)
    retry = campaign_schedule([{'valid_to':'2026-09-20'}],now=datetime(2026,9,20,21,15,tzinfo=UTC))
    assert datetime.fromisoformat(retry['next_fetch_at']) == datetime(2026,9,20,22,15,tzinfo=UTC)


@pytest.mark.parametrize('windows',[[],[{'valid_from':None,'valid_to':None}]])
def test_empty_unknown_or_failed_sources_have_bounded_retries(windows):
    assert datetime.fromisoformat(campaign_schedule(windows,now=NOW)['next_fetch_at']) == NOW+timedelta(hours=12)
    first=campaign_schedule(windows,now=NOW,failed_attempts=1)
    assert datetime.fromisoformat(first['next_fetch_at']) == NOW+timedelta(minutes=15)
    capped=campaign_schedule(windows,now=NOW,failed_attempts=100)
    assert datetime.fromisoformat(capped['next_fetch_at']) == NOW+timedelta(hours=6)


def test_base_refresh_never_waits_for_next_week_and_coalesces_once():
    assert base_fetch_due(NOW,now=NOW,campaign_at=NOW+timedelta(days=7)) == NOW+timedelta(hours=35)
    assert base_fetch_due(NOW,now=NOW,campaign_at=NOW+timedelta(hours=25)) == NOW+timedelta(hours=25)
    assert base_fetch_due(NOW,now=NOW,campaign_at=NOW+timedelta(hours=2)) == NOW+timedelta(hours=35)


def test_daily_offer_times_collect_each_morning_with_bounded_retry():
    from grocery_data.app.services.campaign_refresh_policy import daily_offer_times

    # Wednesday 2026-11-04 05:20 Stockholm (04:20 UTC): Monday's success is stale.
    now = datetime(2026, 11, 4, 4, 20, tzinfo=UTC)
    rows = [{'last_success_at': '2026-11-02T03:34:54+00:00', 'failed_attempts': 0},
            {'last_success_at': '2026-11-04T04:18:00+00:00', 'failed_attempts': 0},
            {'last_success_at': '2026-11-02T03:34:54+00:00', 'failed_attempts': 2,
             'next_fetch_at': '2026-11-04T05:00:00+00:00'}]
    daily_offer_times(rows, now=now)
    assert rows[0]['next_fetch_at'] == now.isoformat()
    assert rows[1]['next_fetch_at'] == '2026-11-05T04:17:00+00:00'
    assert rows[2]['next_fetch_at'] == '2026-11-04T05:00:00+00:00'
    assert {r['reason'] for r in rows} == {'daily_offer_collection'}
    # Missed the morning window: wait for tomorrow, never a daytime collection.
    late = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
    stale = [{'last_success_at': '2026-11-02T03:34:54+00:00'}]
    daily_offer_times(stale, now=late)
    assert stale[0]['next_fetch_at'] == '2026-11-05T04:17:00+00:00'
