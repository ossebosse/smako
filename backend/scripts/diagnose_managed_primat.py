"""Replay real managed Primat path against isolated database/cache copies."""

import asyncio
import json
import shutil
import sqlite3
import tempfile
import traceback
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from grocery_data import __main__ as cli
from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    credential_safe_report,
    production_refresh_lock_path,
)

ROOT = Path("/srv/app/var/price_universes")
DB = Path("/srv/app/var/grocery/grocery_data.sqlite")
OUT = Path("/srv/app/var/reports/recovery-22350-20260914")
events = []
original = cli._collect_production_primat_cache


async def collect(**kwargs):
    try:
        value = await original(**kwargs)
        events.append(
            {
                "stage": "collect_parse_validate_export",
                "status": value["status"],
                "transport": value.get("transport"),
            }
        )
        return value
    except Exception as error:
        events.append(
            {
                "stage": "collect_parse_validate_export",
                "type": type(error).__name__,
                "message": str(error),
                "stack": [
                    {"file": f.filename, "line": f.lineno, "function": f.name}
                    for f in traceback.extract_tb(error.__traceback__)
                ],
            }
        )
        raise


async def no_collection(args):
    return {"results": [], "summary": {}, "cities": ["Lund"]}, 0


async def stop_before_build(**kwargs):
    events.append({"stage": "rebuild_reached", "complete_external_pipeline": True})
    raise RuntimeError("Isolated diagnostic stops before heavy PriceUniverse build")


with RefreshRunLock(production_refresh_lock_path(DB, ROOT)):  # noqa: SIM117
    with tempfile.TemporaryDirectory(prefix="isolated-", dir=OUT) as directory:
        temp = Path(directory)
        with (
            sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as source,
            sqlite3.connect(temp / "copy.sqlite") as target,
        ):
            source.backup(target)
        cache = temp / "cache"
        shutil.copytree(ROOT / "external-provider-cache", cache / "external-provider-cache")
        shutil.copytree(ROOT / "active", cache / "active")
        (cache / "artifacts").mkdir()
        manifest = json.loads((ROOT / "active/city-lund.json").read_bytes())
        shutil.copyfile(ROOT / manifest["artifact_file"], cache / manifest["artifact_file"])
        settings = replace(
            GroceryDataSettings.from_env(),
            database_url="sqlite+pysqlite:///" + str(temp / "copy.sqlite"),
            price_universe_cache_root=cache,
        )
        args = cli._parser().parse_args(
            [
                "daily-refresh",
                "--city",
                "Lund",
                "--postal-code",
                "Lund=22350",
                "--price-universe-cache-root",
                str(cache),
                "--report-dir",
                str(temp / "reports"),
                "--format",
                "json",
            ]
        )
        with (
            patch.object(GroceryDataSettings, "from_env", return_value=settings),
            patch.object(cli, "_run_collect_all", no_collection),
            patch.object(cli, "_collect_production_primat_cache", collect),
            patch.object(cli, "_build_production_price_universe", stop_before_build),
            patch.object(cli, "_emit_refresh_result", lambda *a, **kw: None),
        ):
            code = asyncio.run(cli._daily_refresh_managed(args))
        reports = list((temp / "reports").glob("*.json"))
        report = json.loads(reports[-1].read_bytes()) if reports else {}
        safe = credential_safe_report(
            {
                "events": events,
                "external_provider": report.get("external_provider"),
                "isolation": True,
                "production_activation": False,
                "diagnostic_exit_code": code,
            }
        )
        (OUT / "managed-primat-diagnostic.json").write_text(
            json.dumps(safe, ensure_ascii=False, indent=2)
        )
        print(json.dumps(safe, ensure_ascii=False))
