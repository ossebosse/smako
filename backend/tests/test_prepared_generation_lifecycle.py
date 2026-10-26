"""Derived-cache retention is bounded and cannot publish an older worker."""
import json
from pathlib import Path

import pytest
from app.services import meal_prepared_artifacts as a


@pytest.fixture
def cache(tmp_path,monkeypatch):
    monkeypatch.setenv('RECIPE_PREPARATION_CACHE_ROOT',str(tmp_path/'cache'))
    monkeypatch.setattr(a,'CONTENT_LIMIT',4)
    monkeypatch.setattr(a,'MAX_GENERATIONS',4)
    monkeypatch.setattr(a,'MAX_BYTES',4000)
    version=['v1']
    monkeypatch.setattr(a,'method_signature',lambda:version[0])
    return tmp_path/'cache',version


def test_full_cache_stores_new_generation_and_hits_without_deleting_evidence(cache):
    root,version=cache
    for n in range(3):a.prepared('content',n,lambda n=n:{'v':n})
    directory=root/'content';unknown=directory/'source-evidence.json';unknown.write_bytes(b'unchanged source evidence')
    version[0]='v2'
    with a.shared_preparation({'version':'new'}) as lease:
        for n in range(3):assert a.prepared('content',n,lambda n=n:{'v':100+n})=={'v':100+n}
    assert lease.ready and not lease.failures
    assert unknown.read_bytes()==b'unchanged source evidence'
    assert len(list(directory.glob('*.json')))==4
    assert sum(p.stat().st_size for p in directory.iterdir() if p.is_file())<=a.MAX_BYTES+1
    for n in range(3):assert a.prepared('content',n,lambda:pytest.fail('new generation must persist'))=={'v':100+n}
    version[0]='v1'
    assert a.prepared('content',0,lambda:{'v':0})=={'v':0}  # Correct recompute, never v2 data.


def test_late_old_computation_cannot_replace_new_ready_generation(cache):
    root,version=cache
    new=None
    with a.shared_preparation('old') as old:
        def late():
            nonlocal new
            version[0]='v2'
            with a.shared_preparation('new') as new:
                assert a.prepared('content','new',lambda:{'v':'new'})=={'v':'new'}
            return {'v':'old'}
        assert a.prepared('content','old',late)=={'v':'old'}
    state=json.loads((root/'.shared-generation.json').read_bytes())
    assert new.ready and not old.ready and old.failures
    assert state['token']==new.token and state['state']=='ready'
    assert len(list((root/'content').glob('*.json')))==1
    assert a.prepared('content','new',lambda:pytest.fail('retain new data'))=={'v':'new'}


def test_interruption_leaves_unready_and_restart_completes_with_hits(cache):
    root,_=cache
    with pytest.raises(RuntimeError,match='interrupt'),a.shared_preparation('same'):
        a.prepared('content','first',lambda:{'v':1})
        raise RuntimeError('interrupt')
    assert json.loads((root/'.shared-generation.json').read_bytes())['state']=='preparing'
    with a.shared_preparation('same') as restarted:
        assert a.prepared('content','first',lambda:pytest.fail('reuse exact completed artifact'))=={'v':1}
        a.prepared('content','second',lambda:{'v':2})
    assert restarted.ready
    assert len(list((root/'content').glob('*.json')))==2


def test_owned_interrupted_temporary_is_removed_but_unknown_files_survive(cache):
    root,_=cache;directory=root/'content';directory.mkdir(parents=True)
    temporary=directory/('.derived-'+'a'*64+'-'+'b'*32+'.tmp');temporary.write_bytes(b'partial')
    unknown=directory/'proof.tmp';unknown.write_bytes(b'keep')
    with a.shared_preparation('restart') as lease:
        a.prepared('content','item',lambda:{'v':1})
    assert lease.ready and not temporary.exists() and unknown.read_bytes()==b'keep'


def test_failed_replace_falls_back_then_restart_writes(cache,monkeypatch):
    root,_=cache;replace=a.os.replace
    def fail_cache(source,destination):
        if Path(destination).parent.name=='content':raise OSError('interrupted disk write')
        return replace(source,destination)
    with monkeypatch.context() as patch:
        patch.setattr(a.os,'replace',fail_cache)
        with a.shared_preparation('disk failure') as lease:
            assert a.prepared('content','item',lambda:{'v':1})=={'v':1}
        assert not lease.ready
        assert not list((root/'content').glob('*.tmp'))
    with a.shared_preparation('disk failure') as restarted:
        assert a.prepared('content','item',lambda:{'v':1})=={'v':1}
    assert restarted.ready


def test_unstorable_or_contended_content_never_publishes_ready(cache):
    with a.shared_preparation('partial') as partial:
        assert a.prepared('content','partial',lambda:{'v':1},storable=lambda:False)=={'v':1}
    assert not partial.ready
    with a._content_write_batch(),a.shared_preparation('contender') as contender,a._content_write_batch() as budget:
        a.prepared('content','item',lambda:{'v':1},_write_budget=budget)
    assert not contender.ready


def test_retention_enforces_byte_budget_and_protects_current_requests(cache,monkeypatch):
    root,version=cache
    monkeypatch.setattr(a,'MAX_BYTES',1100)
    for n in range(3):a.prepared('content',n,lambda n=n:{'v':'x'*100,'n':n})
    version[0]='v2'
    with a.shared_preparation('new') as lease:
        for n in range(3):a.prepared('content',n,lambda n=n:{'v':'y'*100,'n':n})
    assert lease.ready
    assert sum(p.stat().st_size for p in (root/'content').glob('*.json'))<=1100
    for n in range(3):assert a.prepared('content',n,lambda:pytest.fail('all three current entries retained'))['n']==n
