"""Replay the immutable live-proven Windows package; collection is forbidden."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

root = Path("D:/smako-local-relay/releases/bdc9f7df4170")
manifest = json.loads((root / "RELEASE.json").read_bytes())
assert manifest["commit"] == "bdc9f7df417084641d0a712e3dad188dad1ad7d4"
for name, digest in manifest["files"].items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
sys.path[:0] = [str(root / "backend"), str(root)]
from grocery_data import local_relay, source_cli
from grocery_data.relay_config import RelayTransport

parser = argparse.ArgumentParser()
parser.add_argument("workspace", type=Path)
parser.add_argument("report", type=Path)
parser.add_argument("--container", default="smako-lund-transition-new")
args = parser.parse_args()
test_root = Path("D:/Projects/Smako/.local/transition").resolve()
assert args.workspace.resolve().is_relative_to(test_root)
assert args.report.resolve().is_relative_to(test_root)
assert args.container in {"smako-lund-transition-new", "smako-lund-transition-receiver"}
os.environ["DEMAND_REFRESH_ENABLED"] = "true"
calls = {"retailer": 0, "push": 0, "activate": 0}
transport = RelayTransport(
    ssh_host="smako",
    container=args.container,
    inbox="/work/raw/source-inbox/municipality-1281",
)


async def forbidden_collect(*args, **kwargs):
    calls["retailer"] += 1
    raise AssertionError("retailer collection forbidden in replay test")


def push(value):
    calls["push"] += 1
    value.transport = transport
    return source_cli.push(value)


def activate(digest):
    calls["activate"] += 1
    return local_relay.remote_activate(digest, transport)


code = local_relay.run(args.workspace, collect=forbidden_collect, push=push, activate=activate)
report = {
    "kind": "guarded replay; not S4U live collection",
    "exit": code,
    "calls": calls,
    "package_commit": manifest["commit"],
    "files_verified": len(manifest["files"]),
}
if (args.workspace / "last-success.json").exists():
    receipt = json.loads((args.workspace / "last-success.json").read_bytes())
    report["receipt"] = {k: v for k, v in receipt.items() if k != "artifact"}
args.report.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
assert code == 0 and calls["retailer"] == 0
