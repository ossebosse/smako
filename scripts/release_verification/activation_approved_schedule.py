"""Read-only schedule calculation and guarded not_due on copied relay state."""

import hashlib
import json
import shutil
import sys
from datetime import UTC, date, datetime, time, timedelta
from itertools import pairwise
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[2]
output = root / '.local/activation-approved-20261001'
package = Path('D:/smako-local-relay/releases/bdc9f7df4170')
release = json.loads((package / 'RELEASE.json').read_bytes())
assert release['commit'] == 'bdc9f7df417084641d0a712e3dad188dad1ad7d4'
for name, digest in release['files'].items():
    assert hashlib.sha256((package / name).read_bytes()).hexdigest() == digest
sys.path[:0] = [str(package / 'backend'), str(package)]
from grocery_data import local_relay

source = root / '.local/drift-verification/s4u/state'
workspace = output / 'not-due-copy'
workspace.mkdir(exist_ok=False)
for name in ['last-success.json', 'source-scope.json']:
    shutil.copy2(source / name, workspace / name)
before = (workspace / 'last-success.json').read_bytes()
receipt = json.loads(before)
assert receipt['sha256'] == '5b1a2b6b01ba65338f224cdd6af432c8178f214b1612d5d54ec400ffe8f9362a'
assert receipt['municipality_code'] == '1281'
counts = {'collection': 0, 'push': 0, 'activation': 0}


async def no_collect(*args, **kwargs):
    counts['collection'] += 1
    raise AssertionError('Collection forbidden in not_due proof')


def no_push(*args, **kwargs):
    counts['push'] += 1
    raise AssertionError('Push forbidden in not_due proof')


def no_activate(*args, **kwargs):
    counts['activation'] += 1
    raise AssertionError('Activation forbidden in not_due proof')


code = local_relay.run(workspace, collect=no_collect, push=no_push, activate=no_activate)
assert code == 0 and not any(counts.values())
assert (workspace / 'last-success.json').read_bytes() == before
assert (source / 'last-success.json').read_bytes() == before
events = [json.loads(line) for p in (workspace / 'logs').glob('*.jsonl') for line in p.read_text().splitlines()]
assert any(e.get('event') == 'not_due' for e in events)
zone = ZoneInfo('Europe/Stockholm')


def starts(first, days):
    return [datetime.combine(first + timedelta(days=day), time(hour, 30), zone).astimezone(UTC)
            for day in range(days) for hour in (1, 9, 17)]


def window(first):
    points = starts(first, 4)
    gaps = [(b - a).total_seconds()/3600 for a, b in pairwise(points)]
    max_gap = max(gaps)
    return {'minimum_gap_hours': min(gaps), 'maximum_gap_hours': max_gap,
            'worst_observation_to_serving_budget_hours': 35 + max_gap + 3,
            'minimum_margin_hours': 48 - (35 + max_gap + 3)}


observed = datetime.fromisoformat(receipt['observed_from'])
due = observed + timedelta(hours=35)
future = starts(date(2026, 10, 2), 5)
attempt = next(t for t in future if t >= due)
stop = observed + timedelta(hours=48)
live = json.loads((root / 'docs/releases/lund-20260929/S4U-LIVE-EVIDENCE.json').read_bytes())
duration = datetime.fromisoformat(live['finished_utc']) - datetime.fromisoformat(live['started_utc'])
report = {
    'checked_utc': datetime.now(UTC).isoformat(),
    'schedule_approved_but_not_registered': True,
    'kind': 'Calculation, not future execution; not_due is guarded execution on copied state',
    'due_hours': 35, 'warning_hours': 36, 'hard_stop_hours': 48,
    'not_due': {'exit': code, 'calls': counts, 'receipt_unchanged': True,
                'original_state_unchanged': True, 'observed_from': receipt['observed_from'],
                'receipt_sha256': hashlib.sha256(before).hexdigest(), 'package_files_verified': len(release['files'])},
    'clock_times_local': ['01:30', '09:30', '17:30'],
    'normal': window(date(2026, 10, 2)),
    'autumn_20261025': window(date(2026, 10, 24)),
    'spring_20270328': window(date(2027, 3, 27)),
    'next_relay_due_local': due.astimezone(zone).isoformat(),
    'projected_collection_start_local': attempt.astimezone(zone).isoformat(),
    'hard_stop_original_observation_local': stop.astimezone(zone).isoformat(),
    'measured_prior_full_delivery_seconds': duration.total_seconds(),
    'projected_serving_with_measured_duration_local': (attempt + duration).astimezone(zone).isoformat(),
    'projected_serving_with_3h_budget_local': (attempt + timedelta(hours=3)).astimezone(zone).isoformat(),
    'margin_with_3h_budget_hours': (stop - attempt - timedelta(hours=3)).total_seconds()/3600,
    'one_missed_poll_worst_case': {'normal_hours_until_serving': 35 + 16 + 3,
                                  'autumn_hours_until_serving': 35 + 17 + 3,
                                  'freshness_guaranteed': False},
    'delay_or_lock': 'Delay consumes margin; a skipped due run or persistent lock can exceed 48h. IgnoreNew/StartWhenAvailable/WakeToRun do not guarantee recovery while computer/network unavailable. Never break locks.',
    'runtime_budget_limit': 'Three hours is a planning bound through serving/reload, not a guarantee. Confirm receiver completion: Windows PT3H alone does not prove remote child operations stopped.',
}
assert report['normal']['minimum_margin_hours'] == 2
assert report['autumn_20261025']['minimum_margin_hours'] == 1
assert report['spring_20270328']['minimum_margin_hours'] == 2
(output / 'approved-schedule-evidence.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
