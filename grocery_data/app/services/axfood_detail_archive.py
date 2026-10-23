"""Exact, bounded Axfood evidence validation shared by reader and collector.

GTINs use the existing checksum-valid GTIN-8/12/13/14 normalizer. Comparison
zero-pads validated values to 14 digits (GS1 representation), never names.
Thirty days is a recheck cadence, not expiry or allergen certification.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from grocery_data.app.domain.identifiers import normalize_gtin

VERSION = "axfood-detail-evidence-v3"
CODE = re.compile(r"[0-9A-Za-z_-]{1,40}\Z")
MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
HOSTS = {
    "willys": {"www.willys.se", "www.willys.prod.axcsfprod.aws.axfoodapp.cloud"},
    "hemkop": {"www.hemkop.se"},
}


@dataclass(frozen=True)
class DetailEvidence:
    status: str
    raw: dict | None = None
    meta: dict | None = None
    digest: str | None = None


def timestamp(value):
    if not isinstance(value, str):
        raise TypeError("Missing observation time")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Observation time must have a timezone")
    return result.astimezone(UTC)


def same_gtin(left, right):
    return (normalize_gtin(left).normalized_gtin.zfill(14)
            == normalize_gtin(right).normalized_gtin.zfill(14))


def validate_pair(payload, metadata, chain, code, *, now=None):
    if chain not in HOSTS or not isinstance(code, str) or not CODE.fullmatch(code):
        return DetailEvidence("invalid_identity")
    try:
        if len(payload) > MAX_DOCUMENT_BYTES or len(metadata) > 65536:
            return DetailEvidence("oversized")
        meta = json.loads(metadata)
        if not isinstance(meta, dict):
            return DetailEvidence("invalid_metadata")
        if meta.get("chain") != chain or meta.get("code") != code:
            return DetailEvidence("metadata_identity_mismatch")
        if type(meta.get("http_status")) is not int or not 100 <= meta["http_status"] <= 599:
            return DetailEvidence("invalid_metadata")
        url = urlsplit(meta.get("url", ""))
        paths = {f"/axfood/rest/p/{code}"}
        if chain == "willys":
            paths.add(f"/axfood/rest/v1/p/{code}")
        if (url.scheme != "https" or url.hostname not in HOSTS[chain]
                or url.port not in (None, 443) or url.username or url.password
                or url.path not in paths or url.query or url.fragment):
            return DetailEvidence("source_url_mismatch")
        observed = timestamp(meta.get("fetched_at"))
        if observed > (now or datetime.now(UTC)) + timedelta(minutes=5):
            return DetailEvidence("future_observation")
        if meta.get("revoked") is True:
            return DetailEvidence("revoked", meta=meta)
        if meta.get("http_status") != 200:
            return DetailEvidence("http_error", meta=meta)
        digest = hashlib.sha256(payload).hexdigest()
        if meta.get("payload_sha256") != digest:
            return DetailEvidence("hash_mismatch")
        raw = json.loads(payload)
        if not isinstance(raw, dict) or raw.get("code") != code:
            return DetailEvidence("payload_identity_mismatch")
        return DetailEvidence("verified", raw, meta, digest)
    except (ValueError, TypeError, UnicodeError, OverflowError):
        return DetailEvidence("corrupt")


def read_document(root, chain, code, *, now=None, manifest=None):
    if chain not in HOSTS or not isinstance(code, str) or not CODE.fullmatch(code):
        return DetailEvidence("invalid_identity")
    root = Path(root).resolve()
    path = root / chain / f"{code}.json"
    meta_path = root / chain / f"{code}.meta.json"
    try:
        for item, limit in ((path, MAX_DOCUMENT_BYTES), (meta_path, 65536)):
            if not item.resolve().is_relative_to(root):
                return DetailEvidence("unsafe_path")
            if item.exists() and item.stat().st_size > limit:
                return DetailEvidence("oversized")
        if not meta_path.is_file():
            return DetailEvidence("corrupt_pair" if path.exists() else "missing")
        # Negative responses intentionally have no raw body, but their source,
        # identity and observation metadata still need validation.
        payload = path.read_bytes() if path.is_file() else b""
        metadata = meta_path.read_bytes()
        if manifest is not None:
            if manifest["files"].get(f"{chain}/{meta_path.name}") != hashlib.sha256(metadata).hexdigest():
                return DetailEvidence("release_file_mismatch")
            if path.is_file() and manifest["files"].get(f"{chain}/{path.name}") != hashlib.sha256(payload).hexdigest():
                return DetailEvidence("release_file_mismatch")
        return validate_pair(payload, metadata, chain, code, now=now)
    except OSError:
        return DetailEvidence("unreadable")


def recheck_state(root, chain, code, *, now=None):
    now = now or datetime.now(UTC)
    evidence = read_document(root, chain, code, now=now)
    if evidence.status == "verified":
        age = now - timestamp(evidence.meta["fetched_at"])
        return "due" if age >= timedelta(days=30) else "verified"
    if evidence.status == "http_error":
        status = evidence.meta["http_status"]
        if status in (404, 410):
            return ("due_missing" if now - timestamp(evidence.meta["fetched_at"])
                    >= timedelta(days=7) else "permanent_missing")
        if status == 429 or status in (401, 403, 405):
            return "access_stopped"
        if status >= 500 or status in (408, 425):
            return "retry"
        return "permanent_error"
    return evidence.status


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f".{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode()


def selection_state(root, chain, code, *, now=None):
    now = now or datetime.now(UTC)
    state = recheck_state(root, chain, code, now=now)
    path = Path(root) / chain / f"{code}.attempt.json"
    if not CODE.fullmatch(code):
        return "invalid_identity"
    try:
        if not path.resolve().is_relative_to(Path(root).resolve()) or path.stat().st_size > 65536:
            return "unsafe_path"
        attempt = json.loads(path.read_bytes())
        if attempt["chain"] != chain or attempt["code"] != code:
            return "corrupt_attempt"
        if attempt.get("access_stopped"):
            return "access_stopped"
        if attempt.get("permanent_error"):
            return "permanent_error"
        if timestamp(attempt["next_check_at"]) > now:
            return "waiting_after_error"
    except FileNotFoundError:
        pass
    except (KeyError, TypeError, ValueError, OSError):
        return "corrupt_attempt"
    return state


def retain_response(root, chain, code, raw, *, now=None, retry_after=None):
    """Write only staging. Failures never replace a verified LKG pair/time."""
    root = Path(root)
    if root.parent.name != "staging" or root.resolve() != root.absolute():
        raise ValueError("Collector writes require staging/<run-id>")
    if chain not in HOSTS or not CODE.fullmatch(code):
        raise ValueError("Invalid chain/code")
    now = now or datetime.now(UTC)
    meta = {"code": code, "chain": chain, "url": raw.url, "query": raw.query,
            "fetched_at": raw.fetched_at.isoformat(), "http_status": raw.http_status,
            "content_type": raw.content_type, "payload_sha256": raw.payload_hash,
            "connector_version": raw.connector_version, "store_external_id": raw.store_external_id}
    metadata = encoded(meta)
    evidence = validate_pair(raw.payload if raw.http_status == 200 else b"", metadata, chain, code, now=now)
    if raw.chain.value != chain or (raw.http_status == 200 and evidence.status != "verified"):
        raise ValueError("Fetched detail did not pass evidence validation")
    if raw.http_status != 200 and evidence.status != "http_error":
        raise ValueError("Fetched error did not pass metadata validation")
    directory = root / chain
    if directory.resolve().parent != root.resolve():
        raise ValueError("Unsafe chain directory")
    path, meta_path = directory / f"{code}.json", directory / f"{code}.meta.json"
    attempt_path = directory / f"{code}.attempt.json"
    if evidence.status == "verified":
        atomic_bytes(path, raw.payload)
        atomic_bytes(meta_path, metadata)
        attempt_path.unlink(missing_ok=True)
        return "verified"
    if read_document(root, chain, code, now=now).status != "verified":
        atomic_bytes(meta_path, metadata)
    status = raw.http_status
    next_check = now + (timedelta(days=7) if status in (404, 410) else timedelta(hours=1))
    if retry_after is not None:
        next_check = max(next_check, now + timedelta(seconds=max(0, retry_after)))
    atomic_bytes(attempt_path, encoded({"code": code, "chain": chain, "http_status": status,
        "attempted_at": now.isoformat(), "next_check_at": next_check.isoformat(),
        "access_stopped": status in (401, 403, 405, 429) or raw.kind in {"access_challenge", "rate_limit"},
        "permanent_error": 400 <= status < 500 and status not in (404, 410, 408, 425, 429)}))
    return "retained_lkg" if read_document(root, chain, code, now=now).status == "verified" else "error"


def publish_release(root, run_id):
    """Under the caller's existing operation lease, atomically freeze a release.

    No active pointer is changed. An incomplete staging pair is rejected, rather
    than mixing revisions or claiming that partial source coverage is complete.
    """
    root = Path(root).resolve()
    from deploy.scripts.storage_maintenance import maintain_axfood_archives

    retention = maintain_axfood_archives(root, now=datetime.now(UTC), apply=False)
    if retention["status"] == "blocked":
        raise ValueError("Archive retention budget blocked")
    if not CODE.fullmatch(run_id):
        raise ValueError("Invalid run ID")
    staging = root / "staging" / run_id
    if not staging.resolve().is_relative_to(root / "staging"):
        raise ValueError("Unsafe staging path")
    files, coverage = {}, {}
    for chain in HOSTS:
        counts = {"verified": 0, "missing": 0, "rejected": 0, "revoked": 0}
        for meta in sorted((staging / chain).glob("*.meta.json")):
            code = meta.name.removesuffix(".meta.json")
            evidence = read_document(staging, chain, code)
            if evidence.status == "verified":
                counts["verified"] += 1
                for name in (f"{code}.json", f"{code}.meta.json"):
                    path = staging / chain / name
                    files[f"{chain}/{name}"] = hashlib.sha256(path.read_bytes()).hexdigest()
            elif evidence.status == "http_error":
                counts["missing"] += evidence.meta["http_status"] in (404, 410)
                counts["rejected"] += evidence.meta["http_status"] not in (404, 410)
                # Negative evidence must survive the next staging copy so a
                # new run cannot accidentally reset the seven-day/backoff gate.
                files[f"{chain}/{meta.name}"] = hashlib.sha256(meta.read_bytes()).hexdigest()
            elif evidence.status == "revoked":
                counts["revoked"] += 1
                files[f"{chain}/{meta.name}"] = hashlib.sha256(meta.read_bytes()).hexdigest()
                payload = meta.with_name(f"{code}.json")
                if payload.exists():
                    body = payload.read_bytes()
                    if len(body) > MAX_DOCUMENT_BYTES or hashlib.sha256(body).hexdigest() != evidence.meta.get("payload_sha256"):
                        raise ValueError("Revoked document hash mismatch")
                    files[f"{chain}/{payload.name}"] = hashlib.sha256(body).hexdigest()
            else:
                raise ValueError(f"Rejected staging pair: {chain}/{code} ({evidence.status})")
            attempt = meta.with_name(f"{code}.attempt.json")
            if attempt.is_file():
                if not attempt.resolve().is_relative_to(staging) or attempt.stat().st_size > 65536:
                    raise ValueError("Unsafe attempt journal")
                files[f"{chain}/{attempt.name}"] = hashlib.sha256(attempt.read_bytes()).hexdigest()
        for payload in (staging / chain).glob("*.json"):
            if not payload.name.endswith((".meta.json", ".attempt.json")) and not payload.with_name(
                    payload.stem + ".meta.json").is_file():
                raise ValueError("Half-written staging pair")
        coverage[chain] = counts
    if not any(row["verified"] or row["revoked"] for row in coverage.values()):
        raise ValueError("No verified documents to publish")
    code_lists = {}
    for path in sorted(staging.glob("codes-*.txt")):
        data = path.read_bytes()
        code_lists[path.name] = {"sha256": hashlib.sha256(data).hexdigest(),
                                 "count": len(data.decode().splitlines())}
        files[path.name] = hashlib.sha256(data).hexdigest()
    for path in sorted(staging.glob("code-source-*.json")):
        files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {"schema": "smako-axfood-release-v1", "validation_version": VERSION,
                "files": files, "coverage": coverage, "code_lists": code_lists}
    digest = hashlib.sha256(encoded(manifest)).hexdigest()
    destination = root / "releases" / digest
    if destination.parent.resolve().parent != root:
        raise ValueError("Unsafe release directory")
    if destination.exists():
        verify_release(destination)
        return destination
    needed = sum((staging / name).stat().st_size for name in files) + len(encoded(manifest))
    if (retention["retained_count"] >= retention["max_count"]
            or retention["retained_bytes"] + needed > retention["max_bytes"]):
        raise ValueError("Candidate release exceeds archive retention budget")
    # Copy just verified pairs into a disposable candidate. Staging retains its
    # retry journal, code list and LKG; the immutable release has no writers.
    candidate = root / "releases" / (".publishing-" + uuid4().hex)
    candidate.mkdir(parents=True)
    try:
        for relative in files:
            path = candidate / relative
            path.parent.mkdir(exist_ok=True)
            shutil.copyfile(staging / relative, path)
        atomic_bytes(candidate / "manifest.json", encoded(manifest))
        verify_release(candidate, expected_digest=digest)
        candidate.rename(destination)
    finally:
        if candidate.exists():
            shutil.rmtree(candidate)
    return destination


def verify_release(directory, *, expected_digest=None):
    directory = Path(directory).resolve()
    path = directory / "manifest.json"
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Release manifest exceeds budget")
    manifest = json.loads(path.read_bytes())
    if (manifest.get("schema") != "smako-axfood-release-v1"
            or manifest.get("validation_version") != VERSION
            or hashlib.sha256(encoded(manifest)).hexdigest() != (expected_digest or directory.name)):
        raise ValueError("Release manifest identity mismatch")
    for relative, digest in manifest["files"].items():
        path = directory / relative
        if (not path.resolve().is_relative_to(directory) or path.stat().st_size > MAX_DOCUMENT_BYTES
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
            raise ValueError("Release file hash mismatch")
    return manifest
