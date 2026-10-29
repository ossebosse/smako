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


def test_coop_source_release_includes_its_explicit_reader_only():
    paths = ['grocery_data/app/connectors/coop/structured_offers.py',
             'backend/app/providers/coop_municipality_offers.py',
             'backend/app/services/personal_planner.py', 'backend/app/config.py']
    assert module.selected_paths(paths) == paths[:2]


def test_coop_source_release_includes_explicit_collection_and_dashboard_dependencies():
    paths = ['grocery_data/scripts/collect_coop_municipality.py',
             'backend/app/services/store_collection_history.py',
             'backend/app/services/store_operations.py', 'backend/app/static/admin.js',
             'grocery_data/scripts/unrelated.py', 'backend/app/static/consumer.js']
    assert module.selected_paths(paths) == paths[:1]
    assert module.selected_paths(paths, include_source_dashboard=True) == paths[:4]


def test_coop_app_backport_preserves_other_collectors_byte_for_byte():
    prefix = b'unchanged prelude\n'
    suffix = b'    elif chain == Chain.HEMKOP and parser_version == "old":\n        old_hemkop()\n'
    old = prefix + b'    elif chain == Chain.COOP and parser_version == "v1":\n        old_coop()\n' + suffix
    new = b'new prelude\n    elif chain == Chain.COOP and parser_version in {"v4"}:\n        safe_coop()\n    elif chain == Chain.HEMKOP and parser_version == "new":\n        new_hemkop()\n'
    result = module.coop_app_backport('grocery_data/app/services/collector.py', old, new)
    assert result == prefix + b'    elif chain == Chain.COOP and parser_version in {"v4"}:\n        safe_coop()\n' + suffix
    with pytest.raises(ValueError):
        module.coop_app_backport('backend/app/config.py', old, new)
