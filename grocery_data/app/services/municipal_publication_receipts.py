"""Shared municipal build/publication receipts; collection never acknowledges reload."""
from datetime import UTC, datetime, timedelta

from grocery_data.app.services.coop_offer_job import read, write


def record_build(runtime, *, city, result, environment=None):
    root, config = runtime.configuration(environment)
    path = runtime.location(root, config)
    if city.casefold() != config["city"].casefold() or not path.exists():
        return
    state = read(path)
    state["built"] = {"universe_id": result["price_universe_id"],
                      "fingerprint": runtime.source_plan(environment=environment)["fingerprint"],
                      "at": datetime.now(UTC).isoformat(), "snapshot_ids": result["snapshot_ids"],
                      "provider_metrics": result.get("provider_metrics", {})}
    write(path, state)


def record_publication(runtime, *, status, disk_universe_id, environment=None):
    root, config = runtime.configuration(environment)
    path = runtime.location(root, config)
    if not path.exists() or status["city"].casefold() != config["city"].casefold():
        return
    state = read(path)
    built = state.get("built", {})
    publication = state.setdefault("publication", {})
    now = datetime.now(UTC)
    publication.update(last_attempt_at=now.isoformat(), refresh_exit_code=status.get("refresh_exit_code"),
                       reload=status.get("runtime_reload"), disk_universe_id=disk_universe_id)
    rolled_back = status.get("disk_manifest_rollback", {}).get("status") in {"restored_previous", "removed_first_candidate", "failed"}
    published = (bool(built.get("universe_id")) and disk_universe_id == built["universe_id"]
                 and status.get("refresh_exit_code") in {0, 2} and not rolled_back)
    if published:
        publication.update(last_published_at=now.isoformat(), published_fingerprint=built["fingerprint"])
    reloaded = published and status.get("runtime_reload", {}).get("new_price_universe_id") == disk_universe_id
    if reloaded:
        publication.update(last_reload_at=now.isoformat(), reloaded_fingerprint=built["fingerprint"], status="reloaded")
        publication.pop("retry_at", None)
    else:
        publication.update(status="publication_or_reload_pending", retry_at=(now + timedelta(minutes=15)).isoformat())
    write(path, state)
