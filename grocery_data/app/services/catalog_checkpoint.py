"""Durable, store-bound Willys traversal checkpoints; never promotion authority.

The ordinary collector and source-artifact verifier still qualify every replay.
Callers hold the existing local collection lease. One file per store bounds growth.
"""
from __future__ import annotations

import gzip
import json
import math
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from time import monotonic

from grocery_data.app.domain import RawBatch, TransportMetrics
from grocery_data.app.services.durable_files import atomic_write_bytes


class CollectionWindowEnded(ValueError):
    pass


class CatalogCheckpoints:
    def __init__(self, root, *, area, boundary, parser_version, deadline=None, now=None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise ValueError("checkpoint directory cannot be a symlink")
        self.area, self.boundary = area, boundary
        self.parser_version = parser_version
        self.deadline = deadline
        self.now = now or (lambda: datetime.now(UTC))
        self.reused_requests = 0
        self.oldest = self.now()
        self.stores = {}
        self.deferred = False

    def _progress(self):
        atomic_write_bytes(self.root / 'progress.json', json.dumps({
            'checked_at': self.now().isoformat(), 'stores': self.stores,
            'reused_requests': self.reused_requests, 'qualification': 'ordinary_collector_required',
        }).encode())

    def _identity(self, store):
        # Raw-reference IDs change on rediscovery; identity and geography do not.
        return {"store_id": store.external_id, "area": self.area.model_dump(mode="json"),
                "boundary_sha256": sha256(json.dumps(
                    {k: v for k, v in self.boundary.items() if k != 'observed_at'}
                    if self.boundary else None, sort_keys=True).encode()).hexdigest(),
                "parser_version": self.parser_version, "schema": 1}

    def _path(self, store):
        return self.root / (sha256(store.external_id.encode()).hexdigest() + ".json.gz")

    def _validate(self, batch, store, discovery):
        from grocery_data.app.services.source_artifact import _willys_completion

        if not batch.documents or any(d.store_external_id != store.external_id for d in batch.documents):
            raise ValueError("checkpoint store mismatch")
        oldest = min(d.fetched_at for d in batch.documents)
        newest = max(d.fetched_at for d in batch.documents)
        if oldest.tzinfo is None or newest > self.now() or self.now() - oldest >= timedelta(hours=24):
            raise ValueError("checkpoint observations outside resume window")
        completion = _willys_completion(discovery.documents + batch.documents,
            area=self.area, boundary=self.boundary, contexts=(store.external_id,))[store.external_id]
        if not batch.catalog_completion or not batch.catalog_completion.is_full_traversal:
            raise ValueError("incomplete checkpoint")
        if completion.products_observed != batch.catalog_completion.products_observed:
            raise ValueError("checkpoint completion mismatch")
        return oldest

    async def fetch(self, store, discovery, fetch):
        path = self._path(store)
        estimate = 1800.0  # Conservative cold start; later use measured traversal + 25%.
        try:
            if path.is_symlink() or path.stat().st_size > 64 * 1024**2:
                raise ValueError("invalid checkpoint file")
            with gzip.open(path, "rb") as handle:
                payload = handle.read(128 * 1024**2 + 1)
            if len(payload) > 128 * 1024**2:
                raise ValueError("oversized checkpoint")
            saved = json.loads(payload)
            data = saved["batch"].encode()
            if saved["identity"] != self._identity(store) or sha256(data).hexdigest() != saved["sha256"]:
                raise ValueError("checkpoint identity or hash mismatch")
            estimate = max(60.0, float(saved["seconds"]) * 1.25)
            if not math.isfinite(estimate):
                estimate = 1800.0
                raise ValueError('checkpoint duration invalid')
            batch = RawBatch.model_validate_json(data)
            oldest = self._validate(batch, store, discovery)
        except (OSError, EOFError, ValueError, KeyError, TypeError):
            pass
        else:
            self.reused_requests += max(len(batch.documents), batch.transport.request_count)
            self.oldest = min(self.oldest, oldest)
            self.stores[store.external_id] = {"stage": "traversal_reused", "observed_at": oldest.isoformat(),
                                             "estimated_seconds": estimate}
            self._progress()
            return batch.model_copy(update={"transport": TransportMetrics()})
        if self.deadline is not None and monotonic() + estimate > self.deadline:
            self.deferred = True
            self.stores[store.external_id] = {"stage": "deferred", "reason": "insufficient_collection_window",
                                             "estimated_seconds": estimate}
            self._progress()
            raise CollectionWindowEnded("next complete store will not fit the collection window")
        started = monotonic()
        batch = await fetch(store)
        oldest = self._validate(batch, store, discovery)
        data = batch.model_dump_json(exclude={"documents": {"__all__": {"payload_hash"}}}).encode()
        saved = {"identity": self._identity(store), "batch": data.decode(),
                 "sha256": sha256(data).hexdigest(), "seconds": monotonic() - started}
        atomic_write_bytes(path, gzip.compress(json.dumps(saved).encode(), compresslevel=1))
        self.oldest = min(self.oldest, oldest)
        self.stores[store.external_id] = {"stage": "traversal_saved", "observed_at": oldest.isoformat(),
                                         "seconds": saved["seconds"]}
        self._progress()
        return batch
