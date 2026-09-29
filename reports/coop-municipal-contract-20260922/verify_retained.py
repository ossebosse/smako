"""Final-code replay; no network and no renewed source observations."""
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from grocery_data.scripts import collect_coop_municipality as pipeline

ROOT = Path(__file__).resolve().parent


async def main():
    summaries = []
    for code in ["1281", "1280"]:
        original = ROOT / "live" / code / "final"
        saved = json.loads((original / "coverage.json").read_bytes())
        inventory_path = ROOT / "live" / code / "inventory/inventory.json"

        async def retained_publications(row, output):
            identity = row["store"]["external_id"]
            old = next(x["pipeline"] for x in saved["inventory"]["stores"]
                       if x["store"]["external_id"] == identity)
            if old["status"] == "failed_publication_discovery":
                raise ValueError(old["reason"])
            output.mkdir()
            result = json.loads(json.dumps(old))
            for i, edition in enumerate(result["editions"], 1):
                source = Path(edition["directory"])
                folder = output / str(i)
                folder.mkdir()
                for name in ["source.pdf", "result.json"]:
                    (folder / name).write_bytes((source / name).read_bytes())
                edition["directory"] = str(folder)
            return result

        pipeline.fetch_publications = retained_publications
        output = ROOT / "final-code-replay" / code
        result = await pipeline.run(code, output, inventory_path=inventory_path,
                                   structured_input=ROOT / "live" / code / "pipeline/collection")
        result["source_fetch_mode"] = "offline_replay_retained_observations_no_network"
        (output / "coverage.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf8")
        assert result["price_universe_count"] == saved["price_universe_count"]
        for row in result["inventory"]["stores"]:
            old = next(x for x in saved["inventory"]["stores"]
                       if x["store"]["external_id"] == row["store"]["external_id"])
            assert row["pipeline"].get("price_universe") == old["pipeline"].get("price_universe")
            assert row["pipeline"].get("observed_at") == old["pipeline"].get("observed_at")
        summaries.append({"municipality": code, "mode": result["source_fetch_mode"],
                          "price_universe_count": result["price_universe_count"],
                          "same_store_counts_and_observations": True})
    # No due price calls, including across restart. Use Lund's successful state.
    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected external price request")
    pipeline.fetch_publications = forbidden
    pipeline.collect = forbidden
    pipeline.project_structured = forbidden
    result = await pipeline.run("1281", ROOT / "no-due-final",
        inventory_path=ROOT / "live/1281/inventory/inventory.json",
        previous_path=ROOT / "final-code-replay/1281/update-selection.json", due_only=True)
    assert result["candidate_status"] == "not_built_no_due_work"
    (ROOT / "final-code-verification.json").write_text(json.dumps({
        "verified_at": datetime.now(UTC).isoformat(), "replay": summaries,
        "no_due_external_price_calls": 0, "empty_replacement_not_created": True,
        "production_activation": False}, indent=2), encoding="utf8")


asyncio.run(main())
