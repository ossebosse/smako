"""Hash-pinned public reference inputs for CI; no database or raw retailer data.

The asset consists only of the credential-free PreparedPriceUniverse JSON and
source-bound public ProductFacts used by the existing offline coverage checks.
Download and report execution are separate; the report itself forbids network.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import urllib.request
from pathlib import Path

MAX_BYTES = 512 * 1024 * 1024


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def unpack(source, destination, expected):
    if source.stat().st_size != expected["compressed_bytes"] or sha(source) != expected["compressed_sha256"]:
        raise ValueError("Reference compressed hash/size mismatch")
    if not 0 < expected["bytes"] <= MAX_BYTES:
        raise ValueError("Reference size outside limit")
    temporary = destination.with_suffix(".next")
    try:
        with gzip.open(source, "rb") as reader, temporary.open("wb") as writer:
            size = 0
            while block := reader.read(1024 * 1024):
                size += len(block)
                if size > expected["bytes"]:
                    raise ValueError("Reference decompressed size exceeds manifest")
                writer.write(block)
        if size != expected["bytes"] or sha(temporary) != expected["sha256"]:
            raise ValueError("Reference content hash/size mismatch")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)


def fetch(manifest_path, output):
    manifest = json.loads(manifest_path.read_bytes())
    if manifest["schema"] != "smako-coverage-reference-v1" or set(manifest["files"]) != {"universe", "facts"}:
        raise ValueError("Unsupported reference manifest")
    output.mkdir(parents=True, exist_ok=True)
    for name, row in manifest["files"].items():
        target = output / (name + ".json")
        if target.exists() and sha(target) == row["sha256"]:
            continue
        # Repository release assets only, pinned in the reviewed manifest.
        if not row["url"].startswith("https://github.com/ossebosse/smako/releases/download/"):
            raise ValueError("Reference URL must be a Smako release asset")
        compressed = output / (name + ".json.gz")
        with urllib.request.urlopen(row["url"], timeout=120) as response, compressed.open("wb") as writer:
            size = 0
            while block := response.read(1024 * 1024):
                size += len(block)
                if size > row["compressed_bytes"] or size > MAX_BYTES:
                    raise ValueError("Reference download exceeds manifest size")
                writer.write(block)
        unpack(compressed, target, row)
    return manifest


def review_projection(path, kind):
    """Reject other document types and common credential/user fields before packaging."""
    raw = path.read_bytes()
    if re.search(rb'"(?:authorization|cookie|set-cookie|password|secret|access_token|refresh_token|email|owner_id|session_id|api_key|accounts|personal_state)"\s*:', raw, re.IGNORECASE):
        raise ValueError("Unexpected sensitive field in reference input")
    if re.search(rb'(?:Bearer\s+[A-Za-z0-9_-]{16,}|sk-[A-Za-z0-9]{20,})', raw):
        raise ValueError("Unexpected credential pattern in reference input")
    value = json.loads(raw)
    if kind == "facts":
        if set(value) != {"facts_version", "facts"} or not isinstance(value["facts"], list):
            raise ValueError("Only public ProductFacts projections can be packaged")
    elif "universe" not in value or "stores" not in value or "products" not in value["universe"]:
        raise ValueError("Only a prepared price universe can be packaged")


def pack(args):
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": "smako-coverage-reference-v1", "name": args.name, "clock": args.clock,
                "source_scope": "Frozen Malmö PriceUniverse 2026-10-23, public reviewed product facts 2026-10-28",
                "includes_private_user_data": False, "files": {}}
    for name in ("universe", "facts"):
        source = getattr(args, name)
        review_projection(source, name)
        destination = output / (name + ".json.gz")
        with (source.open("rb") as reader, destination.open("wb") as target,
              gzip.GzipFile(filename="", fileobj=target, mode="wb", mtime=0) as writer):
            shutil.copyfileobj(reader, writer)
        manifest["files"][name] = {"bytes": source.stat().st_size, "sha256": sha(source),
            "compressed_bytes": destination.stat().st_size, "compressed_sha256": sha(destination),
            "url": f"https://github.com/ossebosse/smako/releases/download/{args.tag}/{name}.json.gz"}
    (output / "reference.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    download = sub.add_parser("fetch")
    download.add_argument("--manifest", type=Path, default=Path("ci/coverage-reference.json"))
    download.add_argument("--output", type=Path, required=True)
    package = sub.add_parser("pack")
    for field in ("universe", "facts", "output"):
        package.add_argument("--" + field, type=Path, required=True)
    for field in ("tag", "clock", "name"):
        package.add_argument("--" + field, required=True)
    arguments = parser.parse_args()
    result = fetch(arguments.manifest, arguments.output) if arguments.command == "fetch" else pack(arguments)
    print(json.dumps({"name": result["name"], "files": {k: v["sha256"] for k, v in result["files"].items()}}))
