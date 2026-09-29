from pathlib import Path
p=Path('backend/tests/test_nutrition_reference.py');s=p.read_text().replace('    monkeypatch.setattr(module, "PATH", path)','    (tmp_path / "slv-20260925.json").write_bytes(module.PATH.with_name("slv-20260925.json").read_bytes())\n    monkeypatch.setattr(module, "PATH", path)');p.write_text(s)
p=Path('backend/tests/test_offer_nutrition_references.py');s=p.read_text().replace("product('Persikor',1,'kg',26.9)","product('Persikor',1000,'g',26.9)");p.write_text(s)
p=Path('reports/purchase-planning-20260925/run_tests.py');s=p.read_text().replace("'test_personal_qualified_facts']","'test_personal_qualified_facts','test_variable_purchase_nutrition']").replace("tests-broad.xml","tests-final.xml").replace("tests-broad.log","tests-final.log");p.write_text(s)
