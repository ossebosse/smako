"""Run existing pytest tests with source isolation and no retailer network.

Works with pytest-xdist (``-n auto``): the root conftest.py installs the same
guard in every worker, and the worker records are merged into one access file.
"""

import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import offline_guard

ROOT = pathlib.Path.cwd().resolve()
OUT = ROOT / ".local/verification"
OUT.mkdir(parents=True, exist_ok=True)
# Keep test databases and subprocess scratch on the workspace volume. A small
# Windows system disk must not fill while the repository has ample capacity.
# Pytest rotates its numbered directories here using its normal retention.
scratch = OUT / "tmp"
scratch.mkdir(exist_ok=True)
os.environ.update(TMP=str(scratch), TEMP=str(scratch), TMPDIR=str(scratch))
label = os.getenv("SMAKO_VERIFY_LABEL", "tests")
save = offline_guard.install(ROOT, label, register=False)
os.environ.update(PYTHON_DOTENV_DISABLED="1", PYTHONDONTWRITEBYTECODE="1")
os.environ[offline_guard.ENV_LABEL] = label
os.environ[offline_guard.ENV_ROOT] = str(ROOT)

import pytest

try:
    code = pytest.main(sys.argv[1:])
finally:
    save()
    offline_guard.merge(ROOT, label)
raise SystemExit(code)
