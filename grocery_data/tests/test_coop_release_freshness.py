"""Coop has no ICA campaign-only age exception; refresh before the hard stop."""
from datetime import UTC, datetime, timedelta

from grocery_data.app.services.coop_municipal_refresh import update_selection
from grocery_data.tests.test_coop_municipality import inventory


def test_campaign_cannot_schedule_coop_after_its_48h_price_stop():
    inv=inventory('1281','Lund');now=datetime(2026,9,22,9,tzinfo=UTC)
    observed=now-timedelta(hours=34)
    success={'status':'partial_candidate','observed_at':observed.isoformat(),
             'windows':[{'valid_from':'2026-09-21','valid_to':'2026-09-27'}]}
    state=update_selection(inv,{'3839':success},now=now)
    row=next(r for r in state['stores'] if r['store_id']=='3839')
    assert row['next_fetch_at']==(observed+timedelta(hours=35)).isoformat()
    assert row['price_hard_stop_at']==(observed+timedelta(hours=48)).isoformat()
    restarted=update_selection(inv,previous=state,now=now+timedelta(hours=2))
    assert '3839' in restarted['due_store_ids']
    failed=update_selection(inv,{'3839':{'status':'failed'}},previous=state,now=now+timedelta(hours=2))
    row=next(r for r in failed['stores'] if r['store_id']=='3839')
    assert row['next_fetch_at']==(now+timedelta(hours=2,minutes=15)).isoformat()
    assert row['last_success']==observed.isoformat()
    assert row['price_hard_stop_at']==(observed+timedelta(hours=48)).isoformat()


def test_nearer_xtra_day_campaign_still_precedes_age_deadline():
    inv=inventory('1281','Lund');now=datetime(2026,9,23,19,tzinfo=UTC)
    state=update_selection(inv,{'3658':{'status':'partial_text_candidate','observed_at':now.isoformat(),
        'windows':[{'valid_from':'2026-09-24','valid_to':'2026-09-27'}]}},now=now)
    row=next(r for r in state['stores'] if r['store_id']=='3658')
    assert row['next_fetch_at']=='2026-09-23T21:00:00+00:00'
    assert row['price_hard_stop_at']==(now+timedelta(hours=48)).isoformat()
