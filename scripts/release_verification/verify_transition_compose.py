"""Render only, with private isolated values; never start a Compose service."""

import json
import os
import subprocess
import sys
from pathlib import Path

base = Path("/var/tmp/smako-repo-release-20260929/transition-verification")
commit, image = sys.argv[1:]
values = dict(
    line.split("=", 1) for line in (base / "new/ops.env").read_text().splitlines() if "=" in line
)
values.update(
    BUILD_ID=commit,
    ACME_EMAIL="isolated@example.invalid",
    RUNTIME_ROOT=str(base / "new"),
    SMAKO_RELEASE_IMAGE=image,
    SOURCE_RELAY_INBOX="/srv/app/var/raw_snapshots/source-inbox/municipality-1281",
    INTERNAL_APP_BASE_URL="http://app:8000",
)
private = base / "new/release-compose-test.env"
values["SMAKO_RELEASE_ENV_FILE"] = str(private)
private.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
private.chmod(0o600)
deploy = base / ("build-" + commit[:12]) / "deploy"
result = subprocess.run(
    [
        "docker",
        "compose",
        "--profile",
        "ops",
        "--env-file",
        str(private),
        "-f",
        str(deploy / "compose.yaml"),
        "-f",
        str(deploy / "compose.release.yaml"),
        "config",
        "--format",
        "json",
    ],
    env={**os.environ, **values},
    capture_output=True,
    check=True,
)
config = json.loads(result.stdout)
services = config["services"]
names = ["app", "migrate", "scheduler", "refresh-once", "backup-once"]
for name in names:
    assert services[name]["image"] == image and "build" not in services[name]
for name in ["app", "scheduler", "refresh-once"]:
    assert services[name]["environment"]["REFRESH_MUNICIPALITY_CODE"] == "1281"
    assert services[name]["environment"]["SOURCE_RELAY_INBOX"] == values["SOURCE_RELAY_INBOX"]
for name, readonly in [("app", True), ("scheduler", False)]:
    for mount in services[name]["volumes"]:
        if mount["target"] in {"/srv/app/var/raw_snapshots", "/srv/app/var/price_universes"}:
            assert mount.get("read_only", False) == readonly
print(
    json.dumps(
        {
            "render_only": True,
            "private_values_omitted": True,
            "pinned_services": {n: services[n]["image"] for n in names},
            "municipality": "1281",
            "separate_inbox": values["SOURCE_RELAY_INBOX"],
            "app_raw_and_prices_readonly": True,
            "receiver_raw_and_prices_writable": True,
            "receiver_reload_target": services["scheduler"]["environment"]["INTERNAL_APP_BASE_URL"],
        }
    )
)
