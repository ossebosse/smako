"""A reviewed purchase relation does not erase the recipe's required cut."""
import pytest
from app.services.content_pack_requirements import compatible as cut_compatible
from app.services.intake_product_links import entries

from backend.tests.test_all_intake_links import product

CASES = [
    ('Ryggbiff Skivad Utvald Sverige', 'beef_quick_cut', 'beef_braising_cut'),
    ('Nötstek Fransyska Sverige', 'beef_roasting_cut', 'beef_quick_cut'),
    ('Lövbiff Skivat Nötinnanlår Sverige', 'beef_inner_round_cut', 'beef_whole_tenderloin_cut'),
    ('Oxfilé Hel Brasilien', 'beef_whole_tenderloin_cut', 'beef_inner_round_cut'),
]


@pytest.mark.parametrize('name,accepted,rejected', CASES)
def test_new_exact_relations_keep_authored_cut_boundaries(name, accepted, rejected):
    key, row = next((k, r) for k, r in entries().items() if r['name'] == 'nötkött')
    evidence = next(e for e in row['evidence'] if e['name'] == name)
    p = product(evidence)
    assert cut_compatible([key, accepted], p, None)
    assert not cut_compatible([key, rejected], p, None)
    p.source_provenance.source_snapshot_id = 'unreviewed-current-snapshot'
    assert not cut_compatible([key, accepted], p, None)
