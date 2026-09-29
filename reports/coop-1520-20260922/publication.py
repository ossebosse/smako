"""Exercise existing publication and rollback on a private disposable pointer."""
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from functools import partial
from pathlib import Path
from time import perf_counter

from grocery_data.app.services.freshness import FreshnessPolicy
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock, production_refresh_lock_path
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore, validate_backend_prepared_universe_artifact


def run():
    started=perf_counter();root=Path('/work');profile=root/'profile'
    prod=Path('/srv/app/var/price_universes');prod_db=Path('/srv/app/var/grocery/grocery_data.sqlite')
    private=root/'publication';private.mkdir(exist_ok=False)
    required=tuple(os.environ['PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS'].split(','))
    validator=partial(validate_backend_prepared_universe_artifact,required_context_ids=required,max_price_age_hours=48)
    baseline=profile/'baseline-acceptance-source-universe.json';candidate=profile/'coop-acceptance-source-universe.json'
    result={'production_activation':False,'private_pointer_only':True,'checks':{}}
    with RefreshRunLock(production_refresh_lock_path(prod_db,prod)):
        before=(prod/'active/city-lund.json').read_bytes()
        store=PreparedUniverseArtifactStore(private/'price-universes')
        base=store.activate(baseline,city='Lund',validator=validator,freshness_policy=FreshnessPolicy())
        result['checks']['baseline_validated']=base.status
        meta=validator(json.loads(baseline.read_bytes()),'Lund')
        result['rollback']={'path':str(baseline),'sha256':hashlib.sha256(baseline.read_bytes()).hexdigest(),
            'oldest_base_observed_at':(meta.oldest_base_observed_at or meta.oldest_observed_at).isoformat(),
            'usable_until':((meta.oldest_base_observed_at or meta.oldest_observed_at)+timedelta(hours=48)).isoformat()}
        added=store.activate(candidate,city='Lund',validator=validator,freshness_policy=FreshnessPolicy())
        result['checks']['candidate_validated']=added.status
        current=store.active_manifest_bytes('Lund')
        broken=private/'broken.json';broken.write_text('{"invalid":"candidate"}')
        try:store.activate(broken,city='Lund',validator=validator,freshness_policy=FreshnessPolicy())
        except (ValueError,TypeError):result['checks']['broken_candidate_rejected']=True
        else:raise AssertionError('broken source admitted')
        assert store.active_manifest_bytes('Lund')==current
        result['checks']['failed_candidate_keeps_lkg']=True
        try:store.activate(candidate,city='Lund',validator=validator,expected_snapshot_ids=['missing-source'])
        except ValueError:result['checks']['missing_lineage_rejected']=True
        else:raise AssertionError('missing source lineage admitted')
        assert store.active_manifest_bytes('Lund')==current
        # Only a test activation clock moves; observations and candidates do not.
        try:store.activate(baseline,city='Lund',validator=validator,freshness_policy=FreshnessPolicy(),
                           activated_at=datetime.now(UTC)+timedelta(hours=48))
        except ValueError:result['checks']['stale_rollback_rejected']=True
        else:raise AssertionError('stale rollback admitted')
        assert store.active_manifest_bytes('Lund')==current
        store.activate(baseline,city='Lund',validator=validator,freshness_policy=FreshnessPolicy())
        restarted=PreparedUniverseArtifactStore(private/'price-universes')
        active=restarted.read_active('Lund')
        assert active.universe_id==base.universe_id
        assert hashlib.sha256(restarted.resolve_active_artifact('Lund').read_bytes()).hexdigest()==active.artifact_sha256
        result['checks']['rollback_and_restart_readback']=True
        assert (prod/'active/city-lund.json').read_bytes()==before
        result['production_manifest_unchanged']=True
        result['production_manifest_sha256']=hashlib.sha256(before).hexdigest()
    result['seconds']=round(perf_counter()-started,3)
    (root/'publication-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False))
