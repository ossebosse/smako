"""Writing references retain reviewed unit alternatives and unknown process losses."""
import hashlib
import json
from pathlib import Path

import pytest
from app.services.meal_library_content import MANIFEST
from app.services.recipe_authoring import library_vocabulary
from app.services.recipe_library import current_recipes


def test_export_keeps_unit_specific_requirements_and_process_contract(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts/recipe_layer'))
    from export_authoring_reference import export

    before = MANIFEST.read_bytes()
    output = tmp_path / 'reference'
    summary = export(output)
    assert MANIFEST.read_bytes() == before
    vocabulary = library_vocabulary(current_recipes())
    rows = json.loads((output / 'ingrediensregister.json').read_bytes())['ingredients']
    assert len({r['key'] for r in rows}) == len(rows) == len(vocabulary)
    options = {(r['key'], option['unit']): (option['unit'], option['requirements'])
               for r in rows for option in r['unit_options']}
    assert options == vocabulary.by_unit
    assert summary['ingredient_unit_identity_count'] == len(options)
    fil = next(r for r in rows if r['key'] == 'filmjölk|as_sold')
    fil_options = {r['unit']: r['requirements'] for r in fil['unit_options']}
    assert {'g', 'ml'} <= fil_options.keys() and fil_options['g'] != fil_options['ml']
    assert fil_options[fil['unit']] == fil['requirements']
    recipes = [json.loads(line) for line in (output / 'befintliga-recept-detaljer.jsonl').read_text(encoding='utf-8').splitlines()]
    gulab = next(r for r in recipes if r['base_id'] == 'smako-indian-gulab-jamun' and r['variant_id'] == 'simple')
    assert gulab['preparation_version'] == 'smako-authored-losses-v3'
    assert any(p['operation'] == 'deep_fry_and_drain' for p in gulab['unmeasured_processes'])
    for item in json.loads((output / 'FILMANIFEST.json').read_bytes())['files']:
        raw = (output / item['file']).read_bytes()
        assert len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['sha256']
    with pytest.raises(ValueError, match='existing exports are preserved'):
        export(output)
