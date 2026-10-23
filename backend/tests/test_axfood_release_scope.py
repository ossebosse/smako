import importlib.util
from pathlib import Path

import pytest


def module():
    spec = importlib.util.spec_from_file_location(
        'axfood_release_scope', Path(__file__).parents[2] / 'scripts/build_source_patch.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_separate_reader_release_excludes_pending_source_and_planner_changes():
    release = module()
    changed = [*release.AXFOOD_READER_FILES,
               'grocery_data/app/providers/ica.py', 'backend/app/services/personal_planner.py',
               'deploy/scripts/storage_maintenance.py']
    assert set(release.selected_paths(changed, axfood_reader_only=True)) == release.AXFOOD_READER_FILES
    with pytest.raises(ValueError, match='every reviewed reader dependency'):
        release.selected_paths(changed[1:], axfood_reader_only=True)
