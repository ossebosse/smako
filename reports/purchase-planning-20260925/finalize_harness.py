from pathlib import Path
p=Path('reports/purchase-planning-20260925/runtime_verify.py');s=p.read_text();s=s.replace('    config = configure(root, mode=mode)\n    apply_test_clock()','''    config = configure(root, mode=mode)
    previous_network = root / f"child-network-{mode}.json"
    if previous_network.exists():
        previous_network.rename(root / f"child-network-{mode}-previous-{time.time_ns()}.json")
    apply_test_clock()''')
s=s.replace('        "grocery_data/app/domain/purchase_terms.py",','''        "grocery_data/app/services/product_declarations.py", "grocery_data/app/data/product_declarations.json",
        "backend/app/services/official_product_facts.py", "backend/app/services/personal_planner.py",
        "backend/app/services/personal_store.py", "backend/app/data/nutrition/slv-20260925.json",
        "grocery_data/app/domain/purchase_terms.py",''');p.write_text(s)
