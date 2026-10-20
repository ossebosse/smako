import base64
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "source_patch_lineage", Path(__file__).resolve().parents[2] / "scripts/build_source_patch.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_runtime_newlines_preserve_exact_byte_identity_for_build_verification():
    original = b"value = 1\r\n"
    runtime = {"files": {"module.py": base64.b64encode(original).decode()}}
    assert module.exact_runtime_base(b"value = 1\n", "module.py", runtime) == original
    assert module.transplant(b"value = 1\n", b"value = 1\n", b"value = 2\n") == b"value = 2\n"


@pytest.mark.parametrize("base,actual", [(b"value = 1\n", b"value = 2\r\n"),
                                         (None, b"unexpected file\n"), (b"existing\n", None)])
def test_runtime_semantic_changes_or_missing_files_are_never_normalized_away(base, actual):
    runtime = {"files": {"module.py": base64.b64encode(actual).decode() if actual is not None else None}}
    with pytest.raises(ValueError, match="differs"):
        module.exact_runtime_base(base, "module.py", runtime)
