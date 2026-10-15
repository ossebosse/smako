"""Actual manufacturer documents; declarations never authorize a campaign."""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from grocery_data.app.services.product_declarations import (
    declarations,
    exact_declaration,
    parse_garant,
)

ROOT = Path(__file__).parents[2]
MANIFEST = ROOT / "reports/offer-expansion-20260924/declaration-import.json"


def test_saved_official_documents_reproduce_registered_declarations():
    manifest = json.loads(MANIFEST.read_bytes())
    for record in manifest:
        result = parse_garant(
            Path(record["document"]).read_bytes(),
            json.loads(Path(record["acquisition"]).read_bytes()),
        )
        assert result in declarations()


@pytest.mark.parametrize('basis', ['g', 'ml'])
def test_garant_explicit_nutrition_basis_is_preserved_without_density(basis):
    # Minimal offline parser fixture, not an independently acquired source.
    body = ('''<meta name="description" content="Kokosmjölk. 250 ml.">
        <script type="application/ld+json">{"itemOffered": {
          "gtin":{"value":{"@value":"7311043017881"}},
          "productName":[{"@value":"KOKOSMJÖLK 17-18%","@language":"sv"}],
          "brand":{"brandName":[{"@value":"GARANT","@language":"sv"}]}}}</script>
        <div id="ingredients-content">Kokosextrakt 53%, vatten.</div>
        <div id="nutrition-content">(per 100 BASIS) Energi 711 kJ/ 172 kcal
          Fett 17 g Kolhydrat 2.5 g Protein 1.8 g</div>'''.replace('BASIS', basis)).encode()
    acquisition = {'url':'https://www.garantskafferiet.se/vara-produkter/test/', 'status':200,
                   'observed_at':'2026-10-15T15:00:00Z', 'sha256':hashlib.sha256(body).hexdigest()}
    parsed = parse_garant(body, acquisition)
    assert parsed['basis_unit'] == basis and parsed['package_unit'] == 'ml'
    assert parsed['nutrition']['protein_g'] == 1.8
    bad = body.replace(b'(per 100 ' + basis.encode() + b')', b'(per 100 g) (per 100 ml)')
    with pytest.raises(ValueError, match='basis'):
        parse_garant(bad, {**acquisition, 'sha256':hashlib.sha256(bad).hexdigest()})


@pytest.mark.parametrize("index", [0, 1])
def test_complete_identity_pack_and_gtin_are_independently_required(index):
    r = declarations()[index]
    args = (r["name"], r["brand"], r["package_quantity"], r["package_unit"])
    assert exact_declaration(*args) == r
    assert exact_declaration(*args, gtin=r["gtin"]) == r
    assert exact_declaration(*args, gtin="7310865004703") is None
    assert exact_declaration(r["name"].split()[0], *args[1:]) is None
    assert exact_declaration(args[0], "Other", *args[2:]) is None
    assert exact_declaration(*args[:2], args[2] + 1, args[3]) is None
    assert exact_declaration(*args, rows=[r, copy.deepcopy(r)]) is None


def test_changed_source_hash_host_and_nutrition_basis_are_not_accepted():
    r = declarations()[0]
    record = json.loads(MANIFEST.read_bytes())[0]
    body = Path(record["document"]).read_bytes()
    for update in (
        {"sha256": "bad"},
        {"url": "https://untrusted.example/product"},
        {"http_status": 403},
    ):
        with pytest.raises(ValueError):
            parse_garant(body, {**r["source"], **update})
    changed = body.replace(b"(per 100 g)", b"(per 100 ml)")
    assert changed != body
    with pytest.raises(ValueError, match="basis"):
        parse_garant(changed, {**r["source"], "sha256": hashlib.sha256(changed).hexdigest()})


def test_actual_arla_declaration_requires_fat_form_and_source_approximate_pack():
    from grocery_data.app.services.product_declarations import parse_declaration

    root = ROOT / "reports/purchase-planning-20260925/sources"
    body = (root / "arla-hushallsost.html").read_bytes()
    acquisition = json.loads((root / "arla-hushallsost-acquisition.json").read_bytes())
    row = parse_declaration(body, acquisition)
    assert row in declarations()
    args = (row["name"], row["brand"], 2200, "g")
    assert exact_declaration(*args) is None
    assert exact_declaration(*args, identity_qualifiers=row["identity_qualifiers"]) == row
    for qualifiers in (
        {"fat_percent": 17.0, "package_basis": "source_approximation"},
        {"fat_percent": 26.0, "package_basis": "source_exact"},
    ):
        assert exact_declaration(*args, identity_qualifiers=qualifiers) is None
    assert (
        exact_declaration(*args[:2], 1100, "g", identity_qualifiers=row["identity_qualifiers"])
        is None
    )
    for update in (
        {"sha256": "changed"},
        {"status": 403},
        {"url": "https://example.org/produkter/ost"},
    ):
        with pytest.raises(ValueError):
            parse_declaration(body, {**acquisition, **update})
    changed = body.replace(b"pr. 100 g", b"pr. 100 ml")
    assert changed != body
    with pytest.raises(ValueError, match="basis"):
        parse_declaration(changed, {**acquisition, "sha256": hashlib.sha256(changed).hexdigest()})
