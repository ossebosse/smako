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


def _commit_extra(git, root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf8")
    git("add", "-A")
    git("commit", "-qm", "extra")
    return git("rev-parse", "HEAD")


def test_test_only_changes_do_not_block_app_release(release):
    module, args, _source, git = release
    root = module.ROOT
    git("checkout", "-q", args.from_commit)
    args.from_commit = _commit_extra(git, root, {
        "requirements-dev.lock": "pytest==8.0.0\n",
        "requirements-dev.txt": "pytest\n",
        "grocery_data/tests/test_x.py": "def test_x():\n    pass\n",
    })
    (root / "backend/app/example.py").write_text("value = 2\n", encoding="utf8")
    args.commit = _commit_extra(git, root, {
        "requirements-dev.lock": "pytest==8.0.0\nexecnet==2.1.2\npytest-xdist==3.8.0\n",
        "requirements-dev.txt": "pytest\npytest-xdist\n",
        "grocery_data/tests/test_x.py": "import pytest\n\n@pytest.mark.slow\ndef test_x():\n    pass\n",
    })
    module.prepare(args)
    review = json.loads((args.workdir / "review.json").read_text(encoding="utf8"))
    assert review


@pytest.mark.parametrize("lock", ["pytest==8.1.0\n", ""])
def test_changed_or_removed_lock_pins_still_block(release, monkeypatch, lock):
    module, args, _source, git = release
    root = module.ROOT
    git("checkout", "-q", args.from_commit)
    args.from_commit = _commit_extra(git, root, {"requirements-dev.lock": "pytest==8.0.0\n"})
    (root / "backend/app/example.py").write_text("value = 2\n", encoding="utf8")
    args.commit = _commit_extra(git, root, {"requirements-dev.lock": lock})
    monkeypatch.setattr(module, "remote", lambda *_: pytest.fail("must stop before SSH"))
    with pytest.raises(ValueError, match="Dependencies/schema/compose"):
        module.prepare(args)


def test_grocery_runtime_change_still_blocks_next_to_tests(release, monkeypatch):
    module, args, _source, git = release
    args.commit = _commit_extra(git, module.ROOT, {
        "grocery_data/tests/test_x.py": "x = 1\n",
        "grocery_data/app/model.py": "x = 1\n",
    })
    monkeypatch.setattr(module, "remote", lambda *_: pytest.fail("must stop before SSH"))
    with pytest.raises(ValueError, match="grocery_data/app/model.py"):
        module.prepare(args)



def test_grocery_already_in_scheduler_stays_at_the_app_image_version(release, monkeypatch):
    module, args, _source, git = release
    root = module.ROOT
    (root / "grocery_data/app").mkdir(parents=True)
    (root / "grocery_data/app/policy.py").write_text("X = 1\n", encoding="utf8")
    (root / "backend/app/user.py").write_text(
        "from grocery_data.app.policy import X\nTEXT = 'a'\n", encoding="utf8")
    git("add", ".")
    git("commit", "-qm", "grocery base")
    args.from_commit = git("rev-parse", "HEAD")
    args.commit = _commit_extra(git, root, {"grocery_data/app/policy.py": "X = 1\nY = 2\n",
                                            "backend/app/user.py": "from grocery_data.app.policy import X\nTEXT = 'b'\n"})
    live = {"backend/app/example.py": base64.b64encode(b"value = 2\n").decode(),
            "backend/app/user.py": base64.b64encode(
                b"from grocery_data.app.policy import X\nTEXT = 'a'\n").decode()}
    monkeypatch.setattr(module, "remote", lambda *_: json.dumps(
        {"image": "sha256:" + "a" * 64, "files": live}).encode())
    # Without the flag the grocery change stops the app-only flow.
    with pytest.raises(ValueError, match="grocery_data/app/policy.py"):
        module.prepare(args)
    args.keep_app_grocery = True
    module.prepare(args)
    review = json.loads((args.workdir / "review.json").read_text())
    assert review["review"]["grocery_kept_at_app_image"] == ["grocery_data/app/policy.py"]
    assert set(review["review"]["files"]) == {"backend/app/user.py"}
    # Changed app code that changes what it takes from kept grocery code stops.
    args.commit = _commit_extra(git, root, {
        "backend/app/user.py": "from grocery_data.app.policy import X, Y\nTEXT = 'b'\n"})
    args.workdir = args.workdir.parent / "out2"
    with pytest.raises(ValueError, match="imports grocery code kept"):
        module.prepare(args)
    # Non-Python grocery files never pass.
    args.commit = _commit_extra(git, root, {"backend/app/user.py": "from grocery_data.app.policy import X\nTEXT = 'b'\n",
                                            "grocery_data/app/data.json": "{}\n"})
    args.workdir = args.workdir.parent / "out3"
    with pytest.raises(ValueError, match="grocery_data/app/data.json"):
        module.prepare(args)
