"""Prove metadata and filesystem preservation with a tiny offline Docker image."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

spec = importlib.util.spec_from_file_location(
    "release_image_config", Path(__file__).resolve().parents[2] / "scripts/beta_release_workers/image_config.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_unsupported_image_metadata_requires_review_instead_of_silent_loss():
    for field in ("Volumes", "OnBuild", "Healthcheck", "ArgsEscaped"):
        with pytest.raises(ValueError, match="full release review"):
            module.flatten_instructions({field: True})


@pytest.mark.skipif(sys.platform != "linux", reason="Offline Docker filesystem proof runs on Linux")
def test_flattened_updates_preserve_configuration_and_files_without_accumulating_layers(tmp_path):
    try:
        subprocess.run(["docker", "info"], capture_output=True, timeout=5, check=True)
    except (OSError, subprocess.SubprocessError):
        pytest.skip("Local Docker daemon unavailable")

    def run(*args):
        return subprocess.check_output(["docker", *args], text=True, stderr=subprocess.PIPE, timeout=90).strip()

    prefix = "smako-retention-fixture-" + uuid4().hex
    tags, containers = [], []
    try:
        (tmp_path / "payload").write_text("original")
        (tmp_path / "Dockerfile").write_text(
            "FROM scratch\nCOPY payload /payload\n"
            'ENV PATH=/usr/bin BUILD_ID=original LITERAL="keep\\$value"\n'
            'WORKDIR /app\nUSER 10001:10001\nEXPOSE 8000/tcp\nCMD ["/not-executed"]\n')
        base_tag = prefix + ":base"
        tags.append(base_tag)
        run("build", "--network=none", "--pull=false", "-t", base_tag, str(tmp_path))
        base = json.loads(run("image", "inspect", base_tag))[0]
        for number in (1, 2):
            tag = prefix + ":" + str(number)
            tags.append(tag)
            expected = module.final_image_config(
                base["Config"], release="fixture-" + str(number), commit="a" * 40, base_image=base["Id"])
            (tmp_path / "payload").write_text("reviewed-" + str(number))
            (tmp_path / "Dockerfile").write_text(
                f"FROM {base_tag} AS patched\nCOPY payload /payload\n"
                + module.flatten_instructions(expected))
            run("build", "--network=none", "--pull=false", "-t", tag, str(tmp_path))
            current = json.loads(run("image", "inspect", tag))[0]
            assert current["Config"] == expected
            assert len(current["RootFS"]["Layers"]) <= 2
            container = run("create", "--network=none", tag)
            containers.append(container)
            destination = tmp_path / f"copied-{number}"
            run("cp", container + ":/payload", str(destination))
            assert destination.read_text() == "reviewed-" + str(number)
            run("rm", container)
            containers.remove(container)
            base, base_tag = current, tag
    finally:
        for container in containers:
            run("rm", container)
        for tag in reversed(tags):
            run("image", "rm", tag)
