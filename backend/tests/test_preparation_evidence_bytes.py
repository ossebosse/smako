"""Cross-document evidence hashes must survive a fresh Git checkout."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def test_committed_preparation_evidence_keeps_exact_hash_bindings() -> None:
    root = Path(__file__).resolve().parents[2] / "docs/reviews/preparation-memory-20261024"

    def read(name: str) -> dict:
        return json.loads((root / name).read_bytes())

    def digest(name: str) -> str:
        return hashlib.sha256((root / name).read_bytes()).hexdigest()

    full = read("full-matrix-current.json")
    inventory = read("cells.json")
    review = read("cross-cell-review-current.json")
    closure = read("completion-status.json")

    assert inventory["current_full_matrix_evidence_sha256"] == digest("full-matrix-current.json")
    assert review["source_summary_sha256"] == digest("full-matrix-current.json")
    assert full["source_pilot_progress_sha256"] == digest("pilot-current.json")
    assert review["reviewer_sha256"] == digest("review_cross_cells.py")
    assert closure["stop_receipt_sha256"] == digest("user-requested-stop.json")
    assert full["closure"] == inventory["closure"] == closure
    assert full["status"] == review["source_summary_status"]
    assert full["measured_cells"] == sum(bool(cell["evidence"]) for cell in full["cells"])
    assert review["checked_comparisons"] == len(review["checks"])
    assert review["pending_comparisons"] == len(review["pending"])
