"""Exercise CLI staging/continuation with real archives and offline clients."""
import hashlib
import importlib
import json
import sys
from contextlib import nullcontext
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.tests.test_axfood_detail_archive import CODE, NOW, raw
from grocery_data.app.services.axfood_detail_archive import (
    publish_release,
    retain_response,
    selection_state,
    verify_release,
)


@pytest.fixture
def cli(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / "scripts"))
    fetch = importlib.import_module("fetch_axfood_product_details")
    monkeypatch.setattr(fetch, "RefreshRunLock", lambda *args: nullcontext())
    monkeypatch.setattr(fetch, "selection_state",
                        lambda *args: selection_state(*args, now=NOW + timedelta(days=1)))
    engine = SimpleNamespace(dispose=lambda: None)
    monkeypatch.setattr("grocery_data.app.storage.create_database_engine", lambda *args: engine)
    monkeypatch.setattr("grocery_data.app.storage.create_session_factory", lambda *args: lambda: nullcontext(None))
    codes = [CODE]
    proof = {"schema": "smako-axfood-code-list-v1", "chain": "willys",
             "codes_sha256": hashlib.sha256((CODE + "\n").encode()).hexdigest(),
             "store_external_ids": ["1"], "catalogs": [{"snapshot_id": "approved"}]}
    monkeypatch.setattr("grocery_data.app.services.axfood_catalogue_queue.approved_catalogue_codes",
                        lambda *args, **kwargs: (codes, proof))
    database = tmp_path / "catalog.sqlite"
    database.touch()
    archive = tmp_path / "archive"
    argv = ["fetch", "--chain", "willys", "--store-id", "1", "--approved-snapshot", "approved",
            "--database", str(database), "--price-universe-root", str(tmp_path / "prices"),
            "--archive-root", str(archive), "--run-id", "next"]
    monkeypatch.setattr(sys, "argv", argv)
    calls = []

    class Client:
        requests_per_second = 1

        def __init__(self, **kwargs):
            pass

        async def fetch_product_detail(self, store, code):
            calls.append(code)
            return raw()

        async def aclose(self):
            pass

    monkeypatch.setattr(fetch, "WillysClient", Client)
    return SimpleNamespace(fetch=fetch, archive=archive, argv=argv, proof=proof, calls=calls)


@pytest.mark.asyncio
async def test_initial_approved_catalogue_run_publishes(cli):
    cli.argv.append("--publish")
    assert await cli.fetch.main() == 0
    release, = (cli.archive / "releases").iterdir()
    manifest = verify_release(release)
    assert manifest["coverage"]["willys"]["verified"] == 1
    assert cli.calls == [CODE]


@pytest.mark.asyncio
@pytest.mark.parametrize("interrupted", [False, True])
async def test_approved_catalogue_and_base_survive_interruption_resume_and_publish(cli, monkeypatch, interrupted):
    seed = cli.archive / "staging/seed"
    retain_response(seed, "willys", CODE, raw(), now=NOW)
    # Both LKG's retry record and a missing own document must survive copying.
    retain_response(seed, "willys", CODE, raw(404), now=NOW)
    retain_response(seed, "hemkop", CODE, raw(404, chain="hemkop"), now=NOW)
    base = publish_release(cli.archive, "seed")
    original = verify_release(base)
    cli.argv.extend(["--base-release", str(base), "--publish"])
    collect = cli.fetch.collect

    async def interrupt(*args):
        raise RuntimeError("Interrupted before collection")

    if interrupted:
        monkeypatch.setattr(cli.fetch, "collect", interrupt)
        with pytest.raises(RuntimeError, match="Interrupted"):
            await cli.fetch.main()
        staging = cli.archive / "staging/next"
        for name in original["files"]:
            if name.startswith(("willys/", "hemkop/")):
                assert (staging / name).read_bytes() == (base / name).read_bytes()
        assert json.loads((staging / "approved-catalogue-willys.json").read_bytes()) == cli.proof
        monkeypatch.setattr(cli.fetch, "collect", collect)
        cli.argv[-3:] = ["--publish"]  # Resume staging without copying a base again.
    assert await cli.fetch.main() == 0
    assert cli.calls == []
    assert verify_release(base) == original
    releases = [p for p in (cli.archive / "releases").iterdir() if p != base]
    assert len(releases) == 1
    updated = releases[0]
    manifest = verify_release(updated)
    assert manifest["coverage"]["willys"]["verified"] == 1
    assert manifest["coverage"]["hemkop"]["missing"] == 1
    for name in original["files"]:
        if name.startswith(("willys/", "hemkop/")):
            assert (updated / name).read_bytes() == (base / name).read_bytes()


@pytest.mark.asyncio
async def test_base_rejects_existing_staging_before_writing_catalogue_proof(cli):
    seed = cli.archive / "staging/seed"
    retain_response(seed, "willys", CODE, raw(), now=NOW)
    base = publish_release(cli.archive, "seed")
    staging = cli.archive / "staging/next"
    staging.mkdir()
    sentinel = staging / "existing.txt"
    sentinel.write_bytes(b"unrelated run")
    cli.argv.extend(["--base-release", str(base)])
    with pytest.raises(SystemExit) as exc:
        await cli.fetch.main()
    assert exc.value.code == 2
    assert list(staging.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == b"unrelated run"
    assert cli.calls == []
