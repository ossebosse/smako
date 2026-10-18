"""Portable release preparation must preserve deployed lineage and Git inputs."""

import argparse
import base64
import importlib
import json
import subprocess
import zipfile

import pytest


@pytest.fixture
def release(tmp_path, monkeypatch):
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts"))
    module = importlib.import_module("beta_release")
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        return (
            subprocess.check_output(["git", "-C", str(repo), *args], stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )

    git("init", "-q")
    git("config", "user.name", "Release test")
    git("config", "user.email", "release-test@example.invalid")
    source = repo / "backend/app/example.py"
    source.parent.mkdir(parents=True)
    source.write_text("value = 1\n", encoding="utf8")
    git("add", ".")
    git("commit", "-qm", "base")
    before = git("rev-parse", "HEAD")
    source.write_text("value = 2\n", encoding="utf8")
    git("add", ".")
    git("commit", "-qm", "candidate")
    commit = git("rev-parse", "HEAD")
    monkeypatch.setattr(module, "ROOT", repo)

    def remote(*_):
        return json.dumps(
            {
                "image": "sha256:" + "a" * 64,
                "files": {"backend/app/example.py": base64.b64encode(b"value = 1\n").decode()},
            }
        ).encode()

    monkeypatch.setattr(module, "remote", remote)
    args = argparse.Namespace(
        from_commit=before, commit=commit, host="test", workdir=tmp_path / "out"
    )
    return module, args, source, git


def test_package_uses_committed_bytes_and_binds_live_hash(release):
    module, args, source, _ = release
    source.write_text("uncommitted = True\n", encoding="utf8")
    module.prepare(args)
    review = json.loads((args.workdir / "review.json").read_text())
    assert review["review"]["base_image"] == "sha256:" + "a" * 64
    with zipfile.ZipFile(args.workdir / "candidate.zip") as archive:
        assert archive.read("backend/app/example.py") == b"value = 2\n"
    assert review["package_sha256"] == module.sha((args.workdir / "candidate.zip").read_bytes())


def test_divergent_live_source_is_not_overwritten(release, monkeypatch):
    module, args, _, _ = release
    monkeypatch.setattr(
        module,
        "remote",
        lambda *_: json.dumps(
            {
                "image": "sha256:" + "a" * 64,
                "files": {"backend/app/example.py": base64.b64encode(b"value = 999\n").decode()},
            }
        ).encode(),
    )
    with pytest.raises(ValueError, match="missing or ambiguous"):
        module.prepare(args)
    assert not (args.workdir / "candidate.zip").exists()


@pytest.mark.parametrize("kind", ["deleted", "dependency", "app-dependency", "schema", "compose", "deploy-script"])
def test_unsupported_changes_stop_before_ssh(release, monkeypatch, kind):
    module, args, source, git = release
    if kind == "deleted":
        source.unlink()
    else:
        path = module.ROOT / {
            "dependency": "backend/requirements.txt",
            "app-dependency": "backend/app/requirements.txt",
            "schema": "grocery_data/alembic/new.py",
            "compose": "deploy/compose.yaml",
            "deploy-script": "deploy/scripts/run.py",
        }[kind]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("change\n")
    git("add", "-A")
    git("commit", "-qm", "unsupported")
    args.commit = git("rev-parse", "HEAD")
    monkeypatch.setattr(module, "remote", lambda *_: pytest.fail("must stop before SSH"))
    with pytest.raises(ValueError):
        module.prepare(args)


def test_app_requirements_module_is_packaged_but_env_example_is_not(release, monkeypatch):
    module, args, _, git = release
    app_path = "backend/app/services/content_pack_requirements.py"
    for name in (app_path, "deploy/.env.production.example"):
        path = module.ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("value = 3\n", encoding="utf8")
    git("add", "-A")
    git("commit", "-qm", "app module and documentation example")
    args.commit = git("rev-parse", "HEAD")
    monkeypatch.setattr(module, "remote", lambda *_: json.dumps({
        "image": "sha256:" + "a" * 64,
        "files": {"backend/app/example.py": base64.b64encode(b"value = 1\n").decode(),
                  app_path: None},
    }).encode())
    module.prepare(args)
    with zipfile.ZipFile(args.workdir / "candidate.zip") as archive:
        assert archive.read(app_path) == b"value = 3\n"
        assert "deploy/.env.production.example" not in archive.namelist()


def test_modified_package_and_unverified_activation_stop_before_ssh(release, monkeypatch):
    module, args, _, _ = release
    module.prepare(args)
    args.command = "build"
    (args.workdir / "candidate.zip").write_bytes(b"tampered")
    monkeypatch.setattr(
        module.subprocess, "Popen", lambda *_a, **_k: pytest.fail("must stop before SSH")
    )
    with pytest.raises(ValueError, match="checksum"):
        module.execute(args)
    args.command = "activate"
    args.checks_passed = False
    with pytest.raises(ValueError, match="Verify the built candidate"):
        module.execute(args)


def test_documentation_only_commit_needs_no_deployment(release, monkeypatch):
    module, args, _, _ = release
    args.from_commit = args.commit
    monkeypatch.setattr(module, "remote", lambda *_: pytest.fail("must not contact beta"))
    with pytest.raises(ValueError, match="No app changes"):
        module.prepare(args)


@pytest.mark.parametrize(
    "path",
    [
        "backend/app/../secret",
        "/backend/app/file.py",
        "backend/app/a b.py",
        "backend/app/secret.sqlite",
        "grocery_data/app/model.py",
    ],
)
def test_unsupported_paths(release, path):
    assert not release[0].valid_path(path)
