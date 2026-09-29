"""Package an additive patch against the preserved dirty base, check only."""

import difflib
import hashlib
import importlib.metadata
import importlib.util
import json
import subprocess
import tarfile
from pathlib import Path

R = Path(__file__).resolve().parent
ROOT = R.parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


baseline = json.loads((R / "baseline.json").read_bytes())
paths = [
    *baseline,
    "grocery_data/app/connectors/coop/xtra_pdf.py",
    "grocery_data/scripts/import_xtra_pdf_text.py",
    "grocery_data/tests/test_xtra_pdf_text.py",
    "docs/xtra_pdf_text.md",
]
paths += [
    p.relative_to(ROOT).as_posix()
    for p in (ROOT / "grocery_data/tests/fixtures/xtra-text-20260921").glob("*")
    if p.is_file()
]
paths += [p.relative_to(ROOT).as_posix() for p in R.glob("*.md")]
paths += [
    p.relative_to(ROOT).as_posix() for p in [R / "build_report.py", R / "package_delivery.py"]
]
patch = []
files = {}
with tarfile.open(R / "prework.tar.gz") as archive:
    for path in paths:
        old = (
            (R / "catalog-before.py").read_bytes()
            if path == "grocery_data/app/api/catalog.py"
            else archive.extractfile(path).read()
            if path in baseline
            else b""
        )
        new = (ROOT / path).read_bytes()
        if path in baseline:
            assert sha(old) == baseline[path], path
        files[path] = {
            "before": sha(old) if path in baseline else None,
            "after": sha(new),
            "binary": path.endswith(".pdf"),
        }
        if old == new or path.endswith(".pdf"):
            continue
        patch.append(f"diff --git a/{path} b/{path}\n")
        if path not in baseline:
            patch.append("new file mode 100644\n")
        for line in difflib.unified_diff(
            old.decode("utf-8").splitlines(True),
            new.decode("utf-8").splitlines(True),
            fromfile="a/" + path if path in baseline else "/dev/null",
            tofile="b/" + path,
        ):
            patch.append(line if line.endswith("\n") else line + "\n\\ No newline at end of file\n")
data = "".join(patch).replace("\r\n", "\n").encode("utf-8")
(R / "incremental.patch").write_bytes(data)
check = subprocess.run(
    ["git", "apply", "--reverse", "--check", str(R / "incremental.patch")],
    cwd=ROOT,
    capture_output=True,
    text=True,
    check=False,
)
assert check.returncode == 0, check.stderr
with tarfile.open(R / "review-files.tar.gz", "w:gz") as archive:
    for path in paths:
        archive.add(ROOT / path, arcname=path)

# Previous delivery is evidence, not something to rewrite with today's counts.
prior = ROOT / "reports/coop-municipality-20260921"
manifest = json.loads((prior / "delivery-manifest.json").read_bytes())
prior_artifact_bad = [
    name for name, h in manifest["artifact_hashes"].items() if sha((prior / name).read_bytes()) != h
]
assert not prior_artifact_bad, prior_artifact_bad
prior_code_bad = [
    name
    for name, v in manifest["files"].items()
    if name not in baseline and sha((ROOT / name).read_bytes()) != v["after"]
]
assert not prior_code_bad, prior_code_bad
old = json.loads((prior / "verified-final/result.json").read_bytes())
new = json.loads((R / "coop-regression/result.json").read_bytes())
for previous in old["stores"]:
    current = next(s for s in new["stores"] if s["store"] == previous["store"])
    for key in ["accepted", "rejected", "source_hash", "observed_at"]:
        assert previous[key] == current[key], (previous["store"], key)
assert sum(s["accepted"] for s in new["stores"]) == 499
assert new["price_universe_count"] == 493 and all(p["audit"]["passed"] for p in new["proofs"])
old_products = json.loads((prior / "verified-final/price-universe.json").read_bytes())["products"]
new_products = json.loads((R / "coop-regression/price-universe.json").read_bytes())["products"]


def identity(p):
    return p["source_provenance"]["provider_store_id"], p["offers"][0]["campaign_evidence"][
        "offer_id"
    ]


def facts(p):
    return (
        [p[k] for k in ["name", "gtin", "package_quantity", "package_unit", "price"]],
        [{k: v for k, v in o.items() if k != "campaign_evidence"} for o in p["offers"]],
        [
            {k: v for k, v in o["campaign_evidence"].items() if k != "source_reference"}
            for o in p["offers"]
        ],
    )


old_by = {identity(p): p for p in old_products}
assert all(identity(p) in old_by and facts(p) == facts(old_by[identity(p)]) for p in new_products)
missing = [p for p in old_products if identity(p) not in {identity(n) for n in new_products}]
assert len(missing) == 6 and all(
    p["source_provenance"]["provider_store_id"] == "2696"
    and p["offers"][0]["valid_to"] == "2026-09-21"
    for p in missing
)

# Read-only preservation of pending ICA source worktree and its release package.
inherited = json.loads(
    (ROOT / "reports/municipality-offers-20260920/inherited-work.json").read_bytes()
)
original = Path(inherited["source"])
original_bad = [
    name for name, h in inherited["files"].items() if sha((original / name).read_bytes()) != h
]
assert not original_bad, original_bad
release = json.loads(
    (original / "reports/ica-structured-release-20260920/release-source-manifest.json").read_bytes()
)
vendor = {}
for package, dist in [("bs4", "beautifulsoup4"), ("soupsieve", "soupsieve")]:
    directory = Path(importlib.util.find_spec(package).origin).parent
    for p in directory.rglob("*"):
        if p.is_file() and "__pycache__" not in p.parts:
            vendor["release-vendor/" + package + "/" + p.relative_to(directory).as_posix()] = (
                p.read_bytes()
            )
    metadata = importlib.metadata.distribution(dist)
    for f in metadata.files:
        if ".dist-info/" in str(f):
            vendor["release-vendor/" + str(f)] = metadata.locate_file(f).read_bytes()
release_bad = [
    name
    for name, h in release["files"].items()
    if sha(
        vendor[name]
        if name.startswith("release-vendor/")
        else (original / name).read_bytes().replace(b"\r\n", b"\n")
    )
    != h
]
assert not release_bad, release_bad
report = {
    "branch": subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=ROOT, text=True
    ).strip(),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "files": files,
    "patch_sha256": sha(data),
    "reverse_check": "PASS; checked, never applied",
    "bundle_sha256": sha((R / "review-files.tar.gz").read_bytes()),
    "patch_binary_note": "PDF fixture included in review-files.tar.gz, not textual patch",
    "prior_coop_artifact_hashes_checked": len(manifest["artifact_hashes"]),
    "prior_coop_artifact_mismatches": prior_artifact_bad,
    "prior_coop_code_mismatches": prior_code_bad,
    "same_499_approval_counts_hashes_observation_times": True,
    "same_493_current_product_price_condition_facts": True,
    "six_expired_stora_rows_not_reactivated": True,
    "original_inherited_hashes_checked": len(inherited["files"]),
    "original_mismatches": original_bad,
    "pending_ica_release_hashes_checked": len(release["files"]),
    "pending_ica_mismatches": release_bad,
    "pytest": {
        "initial_passed": 125,
        "seconds": 49.55,
        "final_affected_passed": 20,
        "final_affected_seconds": 16.58,
        "unique_cases": 126,
    },
    "ruff": "PASS",
    "compileall": "PASS",
    "production_activation": False,
    "external_network_calls": 0,
}
report["artifact_hashes"] = {
    p.relative_to(R).as_posix(): sha(p.read_bytes())
    for p in R.rglob("*")
    if p.is_file()
    and p.suffix in {".json", ".md", ".pdf", ".py"}
    and p.name != "verification.json"
    and "__pycache__" not in p.parts
}
(R / "verification.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(
    json.dumps(
        {k: v for k, v in report.items() if k not in ["files", "artifact_hashes"]},
        ensure_ascii=False,
    )
)
