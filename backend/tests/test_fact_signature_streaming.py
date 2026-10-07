"""Exact compatibility with the issued fact identity; no price/fact relaxation."""
import hashlib
import json
from dataclasses import asdict, dataclass, replace

import pytest
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FACTS_VERSION, facts_version


def previous_signature(facts):
    payload = [[list(k), asdict(v)] for k, v in sorted(facts.items())]
    return FACTS_VERSION + ":" + hashlib.sha256(json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def evidence():
    return ProductFacts(source="retained", source_product_id="p", source_snapshot_id="s",
        nutrition={"protein_g": 3.000000000001, "kcal": 51.2}, nutrition_unit="g",
        ingredients=("mjölk", "ärta"), allergens_present=("mjölk",),
        field_sources={"nutrition": ({"raw_fields": {"a": [1, 2.5, None, True, "åäö"]},
                                         "source": "exact:variant", "hash": "sha256"},)})


def test_exact_issued_canonical_hash_for_order_unicode_nested_values_and_empty():
    for facts in ({}, {("store", "p"): evidence()},
                  {("b", "p"): evidence(), ("a", "p2"): replace(evidence(), conflicts=("energy",))}):
        assert facts_version(facts) == previous_signature(facts)
        assert facts_version(dict(reversed(tuple(facts.items())))) == previous_signature(facts)


@pytest.mark.parametrize("field,value", [
    ("source_snapshot_id", "new"), ("source_product_id", "variant"),
    ("nutrition", {"protein_g": 3.000000000002}), ("conflicts", ("missing",)),
    ("allergens_trace", ("soja",)), ("nutrition_unit", "ml"),
    ("field_sources", {"nutrition": ({"hash": "changed"},)}),
])
def test_changed_critical_evidence_never_inherits_a_previous_hash(field, value):
    original = evidence()
    changed = replace(original, **{field: value})
    assert facts_version({("s", "p"): original}) != facts_version({("s", "p"): changed})
    assert facts_version({("s", "p"): changed}) == previous_signature({("s", "p"): changed})


def test_nested_mutation_and_new_previously_missing_product_are_visible():
    fact = evidence(); facts = {("s", "p"): fact}
    old = facts_version(facts)
    fact.field_sources["nutrition"][0]["raw_fields"]["a"].append("new")
    assert facts_version(facts) != old
    old = facts_version(facts)
    facts[("s", "new")] = evidence()
    assert facts_version(facts) != old
    assert facts_version(facts) == previous_signature(facts)


def test_nested_dataclass_compatibility_and_no_mutation():
    @dataclass(frozen=True)
    class Source:
        hash: str
        values: tuple
    fact = replace(evidence(), field_sources={"x": ({"future": Source("h", (1, "ä"))},)})
    before = asdict(fact)
    assert facts_version({("s", "p"): fact}) == previous_signature({("s", "p"): fact})
    assert asdict(fact) == before
