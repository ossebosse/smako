"""Package only this task's increment over the recorded dirty workspace."""
import difflib
import hashlib
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXISTING = [
    "backend/app/models/provenance.py", "backend/app/providers/own.py",
    "backend/app/services/price_universe.py", "backend/app/services/production_price_universe_build.py",
    "backend/app/services/basket_auditor.py", "backend/app/services/basket_calculator.py",
    "deploy/scripts/run_daily_refresh.py", "docs/HANDOFF.md", "grocery_data/__main__.py",
    "grocery_data/app/services/coop_offer_job.py", "grocery_data/app/services/offer_rows.py",
    "grocery_data/app/connectors/citygross/connector.py", "grocery_data/app/connectors/citygross/parser.py",
    "grocery_data/tests/test_citygross_full_acceptance.py",
]
NEW = [
    "backend/app/providers/citygross_municipality.py", "docs/citygross_municipality.md",
    "grocery_data/app/connectors/citygross/municipality_inventory.py",
    "grocery_data/app/connectors/citygross/row_approved_offers.py",
    "grocery_data/app/services/citygross_municipal_job.py",
    "grocery_data/app/services/municipal_publication_receipts.py",
    "grocery_data/scripts/collect_citygross_municipality.py",
    "grocery_data/scripts/replay_citygross_municipality.py",
    "backend/tests/test_citygross_municipality_provider.py",
    "backend/tests/test_citygross_purchase_limits.py",
    "backend/tests/test_citygross_refresh_wiring.py",
    "backend/tests/test_citygross_universe_limits.py",
    "grocery_data/tests/test_citygross_municipality.py",
    "grocery_data/tests/test_citygross_municipal_job.py",
    "grocery_data/tests/test_citygross_offer_semantics.py",
    "grocery_data/tests/test_citygross_partial_lkg.py",
    "grocery_data/tests/fixtures/citygross/municipal-promotion-evidence-20260923.json",
]


def digest(data):
    return hashlib.sha256(data).hexdigest()


patch, rows = [], []
for name in EXISTING + NEW:
    after = (ROOT / name).read_bytes()
    before = b""
    if name in EXISTING:
        options = [HERE / "backups" / name, HERE / "backups" / name.replace("/", "__")]
        backup = next((p for p in options if p.exists()), None)
        if backup is None:
            raise ValueError(f"Missing baseline backup: {name}")
        before = backup.read_bytes()
    rows.append({"path": name, "operation": "modified" if name in EXISTING else "new",
                 "before_sha256": digest(before) if name in EXISTING else None,
                 "after_sha256": digest(after), "bytes": len(after)})
    # Show semantic text changes without CRLF/LF noise. Exact byte hashes and
    # final source payload remain available in the manifest/archive.
    patch.extend(difflib.unified_diff([s + "\n" for s in before.decode("utf-8-sig").splitlines()],
        [s + "\n" for s in after.decode("utf-8-sig").splitlines()],
        fromfile="a/" + name if name in EXISTING else "/dev/null", tofile="b/" + name))
(HERE / "changes.patch").write_text("".join(patch), encoding="utf-8", newline="")
initial = json.loads((HERE / "initial-state.json").read_text(encoding="utf-8-sig"))
preserved = [{"path": name, "initial_sha256": sha,
              "current_sha256": digest((ROOT / name).read_bytes()),
              "unchanged": digest((ROOT / name).read_bytes()) == sha}
             for name, sha in initial["preserved_willys_sha256"].items()]
assert all(r["unchanged"] for r in preserved), "Willys preservation failure"
manifest = {"created_at": datetime.now(UTC).isoformat(),
    "baseline": "recorded dirty workspace, not clean git HEAD", "head": initial["head"],
    "files": rows, "preserved_willys": preserved, "production_activation": False,
    "patch_sha256": digest((HERE / "changes.patch").read_bytes())}
(HERE / "release-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
with zipfile.ZipFile(HERE / "citygross-source-increment.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for name in EXISTING + NEW:
        z.write(ROOT / name, name)
    reports = [*HERE.glob("*.md"), *(HERE / name for name in (
        "changes.patch", "release-manifest.json", "initial-state.json", "tests-summary.json",
        "offer-examples.json", "price-semantics-source-audit.json", "willys-gaps-public-evidence.json",
        "base-current.json", "compileall.json", "ruff-final.log", "runtime-final/ACCEPTANCE.json",
        "runtime_verify.py", "verify_purchases.py", "verify_historical_member_fixture.py"))]
    for report in reports:
        z.write(report, report.relative_to(ROOT).as_posix())
print(json.dumps({"source_files": len(rows), "preserved_willys": len(preserved),
                  "patch_bytes": (HERE / "changes.patch").stat().st_size}))
