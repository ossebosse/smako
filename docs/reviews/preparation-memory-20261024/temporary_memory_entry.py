"""Isolated serialization and overlapping-version memory probe, no menu/audit.

The synthetic next key changes only source_strategy_version. Exact catalogue,
product digest, facts and all observation timestamps remain frozen. Both live
versions stay referenced during the atomic swap, as for an admitted old reader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from app.services.meal_prepared_artifacts import method_signature
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.planner_memory import release_idle_memory
from app.services.price_universe import PriceUniverseKey
from app.services.price_universe_runtime import PreparedPriceUniverseManager


def memory():
    result = {}
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith(('VmRSS:', 'VmHWM:')):
            key, value, _ = line.split()
            result[key.rstrip(':')] = int(value) * 1024
    for key in ('current', 'peak'):
        result['cgroup_' + key] = int(Path('/sys/fs/cgroup/memory.' + key).read_text())
    for key in ('current', 'max'):
        path = Path('/sys/fs/cgroup/memory.swap.' + key)
        result['swap_' + key] = path.read_text().strip() if path.exists() else None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--runtime-cleanup-only', action='store_true',
                        help='Do not add caller-side GC/trim between the ordinary runtime operations')
    args = parser.parse_args()
    started = time.perf_counter()
    manifest = json.loads((args.inputs / 'matrix-inputs.json').read_bytes())
    raw = (args.inputs / 'combined-prices.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest['sha256']['combined-prices.json']
    # Construct a distinct synthetic version before loading either active graph;
    # fixture construction is recorded, and never changes shared frozen inputs.
    candidate = json.loads(raw)
    del raw
    original_key = PriceUniverseKey.model_validate(candidate['universe']['key'])
    next_key = PriceUniverseKey.model_validate({**candidate['universe']['key'],
        'source_strategy_version': 'synthetic-memory-overlap-v1'})
    assert next_key.scope_id == original_key.scope_id
    assert next_key.universe_id != original_key.universe_id
    candidate['universe']['key'] = next_key.model_dump(mode='json')
    candidate['universe']['universe_id'] = next_key.universe_id
    next_path = args.output / 'synthetic-next-prices.json'
    next_path.write_text(json.dumps(candidate, ensure_ascii=False, separators=(',', ':')), encoding='utf8')
    del candidate
    if not args.runtime_cleanup_only:
        release_idle_memory()
    report = {'schema': 'smako-temporary-catalogue-memory-v1',
        'status': 'DIAGNOSTIC_ONLY_NO_MENU_OR_AUDIT', 'inputs': manifest,
        'method_signature': method_signature(),
        'caller_phase_cleanup': not args.runtime_cleanup_only,
        'old_universe': original_key.universe_id, 'new_universe': next_key.universe_id,
        'source_strategy_change_is_synthetic': True, 'stages': []}
    def mark(stage):
        report['stages'].append({'stage': stage, 'elapsed_seconds': time.perf_counter()-started,
                                'memory': memory()})
        (args.output / 'temporary-memory.json').write_text(json.dumps(report, indent=2)+'\n')

    mark('fixture_created_before_load')
    manager = PreparedPriceUniverseManager()
    old = manager.load_file_and_activate(args.inputs / 'combined-prices.json')
    raw = (args.inputs / 'combined-facts.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == manifest['sha256']['combined-facts.json']
    data = json.loads(raw)
    facts = FactsCollection({tuple(key): ProductFacts(**value) for key, value in data['facts']},
                           source_manifests=data.get('source_manifests', ()))
    assert facts.version == data['facts_version']
    del data, raw
    if not args.runtime_cleanup_only:
        release_idle_memory()
    mark('old_active_with_facts')
    mark('before_ordinary_write_artifact')
    serialized = args.output / 'serialized-current.json'
    manager.write_artifact(old, serialized)
    with serialized.open('rb') as handle:
        report['serialized_sha256'] = hashlib.file_digest(handle, 'sha256').hexdigest()
    report['serialized_bytes'] = serialized.stat().st_size
    mark('ordinary_write_artifact_complete')
    if not args.runtime_cleanup_only:
        release_idle_memory()
    mark('before_overlapping_version_load')
    new = manager.load_file_and_activate(next_path)
    assert manager.get_active(next_key.scope_id) is new
    assert old.universe.products_digest == new.universe.products_digest
    assert old.oldest_observed_at == new.oldest_observed_at
    assert len(old.universe.products) == len(new.universe.products)
    report['held_old_products'] = len(old.universe.products)
    report['held_new_products'] = len(new.universe.products)
    report['held_fact_rows'] = len(facts)
    mark('atomic_swap_completed_with_old_reader_alive')
    report['memory_target_passed'] = memory()['cgroup_peak'] <= 2684354560
    mark('complete')
    final = memory()
    (args.output/'final-resource.json').write_text(json.dumps({
        'memory':final,'memory_target_passed':final['cgroup_peak'] <= 2684354560,
        'entry_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'scope':'after all stages and report serialization; before this tiny receipt'},indent=2)+'\n',encoding='utf8')
    if final['cgroup_peak'] > 2684354560:
        raise RuntimeError('Temporary catalogue memory exceeded the 2.5 GiB target')


if __name__ == '__main__':
    main()
