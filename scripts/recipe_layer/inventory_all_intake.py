"""Inspect retained product evidence for every intake ingredient; suggestions are not bindings."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from app.services.ingredient_normalizer import _search_text
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.product_search import ProductSearchRequest


def inspect(args):
    artifact = PreparedPriceUniverseArtifact.from_file(args.universe).restore()
    facts = {tuple(k): v for k, v in json.loads(args.facts.read_bytes())["facts"]}
    blockers = json.loads(args.blockers.read_bytes())["identities"]
    labels = [_search_text(p.name) for p in artifact.universe.products]
    results = []
    for row in blockers:
        name, form = row["identity"].split("|")
        query = {"breda risnudlar": "risnudlar", "runda risnudlar": "risnudlar",
                 "rimmat fläsk": "fläsk", "grön matbanan": "matbanan",
                 "råa räkor": "räkor", "kalvlägg med ben": "kalvlägg"}.get(name, name)
        alternatives = {
            "tamarindpasta": ["tamarind"], "äppelcidervinäger": ["vinäger"],
            "masa harina": ["masa", "majsmjöl", "majsstärkelse"], "pärlkorn": ["korn", "kornris", "matkorn"], "senapsfrön": ["senapsfrö"],
            "klibbigt ris": ["sticky"], "havregrädde": ["imat"], "bambuskott": ["bambu"],
            "tapiokastärkelse": ["tapioka"], "tapiokapärlor": ["tapioka"],
            "gula ärtor": ["ärtor gula", "gula ärter"], "kokosflingor": ["kokos", "riven kokos"],
            "röd currypasta": ["curry"], "klibbigt rismjöl": ["glutinous"],
            "rispapper": ["rice paper"], "rökt lax": ["kallrökt"],
            "uradlinser": ["urad"], "chana dal": ["chana"], "vattenkastanjer": ["kastanjer"],
            "silkestofu": ["silken"], "fjälster": ["fjälster"], "fläsklever": ["lever"],
            "fläsksida med svål": ["fläsksida"], "kalvlägg med ben": ["kalvlägg"],
            "matbanan": ["plantain"], "grön matbanan": ["plantain"],
            "risvermicelli": ["vermicelli"], "svarta linser": ["beluga"],
            "vegansk smördeg": ["smördeg"], "edamame i balja": ["edamame"],
            "popcornmajs": ["popcorn"], "psylliumfröskal": ["psyllium"],
            "risflingor": ["risflingor"], "rökt makrill": ["makrill"],
            "grädde": ["vispgrädde"], "nötkött": ["högrev", "grytbitar"],
            "lammkött": ["lamm"], "lingon": ["lingon frysta"],
        }.get(name, [])
        positions = set()
        for term in [query, *alternatives]:
            found, _, _ = artifact.product_search_index.retrieve(ProductSearchRequest(query=term))
            positions.update(i for key in found for i in artifact.product_search_index.groups[key])
            tokens = _search_text(term).split()
            positions.update(i for i, label in enumerate(labels) if all(t in label for t in tokens))
        products = [artifact.universe.products[i] for i in sorted(positions)]
        candidates, seen = [], set()
        for p in products:
            key = (p.name, p.brand, p.package_quantity, p.package_unit, p.usable_quantity, p.usable_unit)
            if key in seen:
                continue
            seen.add(key)
            f = facts.get((p.store_id, p.product_id))
            valid = bool(f and p.source_provenance and f["source_product_id"] == p.product_id
                         and f["source_snapshot_id"] == p.source_provenance.source_snapshot_id)
            label = _search_text(p.name)
            brand = _search_text(p.brand or "")
            if brand and label.startswith(brand + " "):
                label = label[len(brand) + 1:]
            score = len(set(_search_text(name).split()) ^ set(label.split()))
            if re.search(r"hund|katt|djurfoder|djurmat|hundmat|kattmat", _search_text(p.category or "")):
                score += 100
            if form == "raw_edible" and re.search(r"tork|pulver|krydd|kokt|sylt|marmelad|saft|juice|smak", label):
                score += 10
            candidates.append({"score": score, "product": p.model_dump(mode="json"),
                               "facts": f if valid else None, "exact_facts": valid})
        candidates.sort(key=lambda r: (r["score"], r["product"]["name"], r["product"]["store_id"]))
        results.append({"identity": row["identity"], "affected_variants": row["affected_variants"],
                        "retrieved_products": len(products), "unique_labels": len(candidates),
                        "candidates": candidates})
    report = {"schema": "smako-all-intake-product-research-v1", "status": "unapproved_suggestions",
              "universe_sha256": hashlib.sha256(args.universe.read_bytes()).hexdigest(),
              "facts_sha256": hashlib.sha256(args.facts.read_bytes()).hexdigest(), "identities": results}
    args.output.parent.mkdir(exist_ok=True, parents=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print({"identities": len(results), "with_suggestions": sum(bool(r["candidates"]) for r in results)})


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--universe", type=Path, required=True)
    p.add_argument("--facts", type=Path, required=True)
    p.add_argument("--blockers", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    inspect(p.parse_args())
