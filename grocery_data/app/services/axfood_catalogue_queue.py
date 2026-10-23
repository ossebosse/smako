"""Use approved catalogue rows as the detail queue; no second queue database.

Every promotion makes its new exact codes eligible immediately. Collection's
existing retained-document/negative journal decides which are due. Delisted
codes disappear from the current queue. Reading this view starts no requests.
"""
import hashlib

from sqlalchemy import select

from grocery_data.app.domain import CoverageLevel, SnapshotState, is_complete_catalog_coverage
from grocery_data.app.services.axfood_detail_archive import CODE, encoded
from grocery_data.app.storage.models import CatalogSnapshotModel, ProductModel

MAX_CODES = 100_000


def approved_catalogue_codes(session, snapshot_id, *, chain, store_id):
    row = session.get(CatalogSnapshotModel, snapshot_id)
    if (row is None or chain not in {"willys", "hemkop"} or row.chain != chain
            or not row.is_active or row.state != SnapshotState.PROMOTED.value
            or row.promoted_at is None or row.health_checked_at is None
            or not is_complete_catalog_coverage(CoverageLevel(row.coverage))):
        raise ValueError("Detail queue requires this chain's current approved complete catalogue")
    codes = list(session.scalars(select(ProductModel.external_product_id).where(
        ProductModel.catalog_snapshot_id == snapshot_id, ProductModel.chain == chain,
        ProductModel.store_external_id == store_id).distinct().order_by(
            ProductModel.external_product_id).limit(MAX_CODES + 1)))
    if (not codes or len(codes) > MAX_CODES
            or any(not isinstance(code, str) or not CODE.fullmatch(code) for code in codes)):
        raise ValueError("Approved store's exact code queue is empty, unsafe or exceeds its bound")
    code_hash = hashlib.sha256(("\n".join(codes) + "\n").encode()).hexdigest()
    proof = {"schema": "smako-axfood-code-list-v1", "chain": chain,
        "codes_sha256": code_hash, "store_external_ids": [store_id], "catalogs": [{
            "snapshot_id": row.id, "scope_key": row.scope_key,
            "promoted_at": row.promoted_at.isoformat(), "schema_fingerprint": row.schema_fingerprint,
            "metrics_sha256": hashlib.sha256(encoded(row.metrics)).hexdigest(),
            "codes_sha256": code_hash, "codes": len(codes)}],
        "queue": "current_approved_catalogue_rows", "max_codes": MAX_CODES}
    return codes, proof
