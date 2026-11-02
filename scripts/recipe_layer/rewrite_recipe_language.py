"""Reviewed language successors; old packs and all purchase facts stay immutable.

Run with --prepare, inspect the change report, then --publish. The publication
receipt binds the old manifest, every change and the new immutable packs.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections import Counter

from app.services.meal_library_content import (
    ROOT,
    encoded,
    identity,
    import_pack,
    load_entries,
    manifest_entries,
    validate_pack_bytes,
)
from app.services.recipe_library import _scaled, current_recipes, supports_servings

REPORT = ROOT.parents[3] / "docs/reviews/recipe-language-20261102"
WORK = ROOT.parents[3] / ".local/recipe-language-20261102"
WAIT = "Låt momentet fortsätta tills den angivna tiden och färdighetskontrollen är uppnådda."
PREFIX = "Förbered och påbörja momentet: "
ROOT_VEGETABLES = {"potatis", "sötpotatis", "morot", "palsternacka", "rotselleri", "kålrot", "rödbeta", "rädisa", "rättika", "jordärtskocka"}


def sha(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def shorten_name(name, overrides):
    name = overrides.get(name, name)
    return re.sub(r" – (?:enkel|utökad|vardag|standard)(?= – |$)", "", name)


def rewrite_step(text, recipe, step):
    text = text.replace(PREFIX, "")
    names = {key.split("|")[0] for key in step["ingredient_keys"]}
    if not names & ROOT_VEGETABLES:
        text = text.replace("; skala rotfrukter före vägning", "")
    else:
        text = text.replace("skala rotfrukter före vägning", "skala rotfrukterna innan du väger dem")
    replacements = {
        "Fördela samtliga komponenter mellan fyra portioner.": "Fördela rätten och alla tillbehör mellan fyra portioner.",
        "Fördela varje komponent jämnt mellan portionerna.": "Fördela maten jämnt mellan portionerna.",
        "Fördela hela de angivna komponentmängderna till en portion.": "Servera hela mängden som en portion.",
        "Fördela hela de angivna komponentmängderna över det angivna antalet portioner.": "Fördela hela mängden jämnt mellan portionerna.",
        "Servera huvudkomponenten och samtliga tillbehör tillsammans.": "Servera rätten med alla tillbehör.",
        "Servera huvudrätten tillsammans med samtliga tillagade tillbehör och såser.": "Servera rätten med alla tillbehör och såser.",
        "hela den angivna mängden av huvudkomponenten": "hela mängden av huvudrätten",
        "huvudkomponentens olja": "oljan till huvudrätten",
        "huvudkomponentens salt": "saltet till huvudrätten",
        "huvudkomponentens grönsaker": "grönsakerna till huvudrätten",
        "från huvudkomponenten": "som hör till huvudrätten",
        "komponentens dressing": "dressingen",
        "; ingen förlustandel antas": "",
        "; inget bestämt utbyte antas": "",
        "; det kokspadet kasseras sedan med okänd förlust.": ". Häll sedan bort kokspadet.",
        "; den specificerade typen måste verifieras vid produktval.": ". Kontrollera typen på förpackningen.",
        "detta är ett tillbehör för direkt servering, inte en hållbarhetsverifierad inläggning.": "servera tillbehöret direkt. Receptet är inte avsett för långtidsförvaring.",
        "Detta är för direkt servering, inte en hållbarhetsverifierad konserv.": "Servera direkt. Receptet är inte avsett för långtidsförvaring.",
        "; osten är inte verifierad som Pecorino Romano": "",
        "Tillsätt direkt från frysen när ingrediensen används i instruktionen; den ska inte skalas, ansas eller hackas på nytt.": "Tillsätt direkt från frysen i det steg där råvaran används. Du behöver inte ansa eller hacka den.",
        "Behåll hela den uppvägda ätliga mängden.": "Använd hela den uppvägda mängden.",
        "Planera 720 minuter": "Räkna med 12 timmar",
        "Planera 1440 minuter": "Räkna med 24 timmar",
    }
    for before, after in replacements.items():
        text = text.replace(before, after)
    vague = "Finhacka fasta bitar och färska örter. "
    if vague in text:
        # Exact reviewed preparatory actions, only for ingredients in this step.
        forms = {i["canonical_name"]: i["form"] for i in recipe["ingredients"]}
        frozen = {i["canonical_name"] for i in recipe["ingredients"] if "frozen" in i.get("product_requirements", [])}
        actions = []
        if "fetaost" in names:
            actions.append("Smula fetaosten.")
        if "pepparrot" in names:
            actions.append("Riv pepparroten fint.")
        chopped = [name for name in ("gurka", "vitlök", "persilja", "dill", "mynta", "gräslök", "koriander", "basilika", "valnötter", "oliver", "kapris", "rödlök")
                   if name in names and forms.get(name) not in {"dry"} and name not in frozen]
        if chopped:
            joined = " och ".join([", ".join(chopped[:-1]), chopped[-1]]) if len(chopped) > 1 else chopped[0]
            actions.append("Finhacka " + joined + ".")
        text = text.replace(vague, " ".join(actions) + (" " if actions else ""))
        if text.startswith(("Nöt-örtströssel:", "Fetaörtströssel:")):
            text = text.replace("Rör ihop ", "Blanda ").replace(" till en jämn röra.", ".")
    return text


def batch_basis(recipe):
    design = recipe["design"]
    if design.get("batch_scaling"):
        return copy.deepcopy(design["batch_scaling"])
    steps = design["steps"]
    index = next((n for n, step in enumerate(steps) if n > 0 and step["duration_minutes"] >= 10
                  and (recipe["servings"] == 2 or re.search(r"grädda|stek|baka|sjud|koka", step["text"].casefold()))
                  and not (design["version"] in {"1.3.0", "1.4.0"} and step["id"] in {"rice", "prebake"})), 0)
    return {"step_id": steps[index]["id"], "duration_minutes": steps[index]["duration_minutes"]}


def rewrite_recipe(original, overrides):
    row = copy.deepcopy(original)
    row["name"] = shorten_name(row["name"], overrides)
    design = row["design"]
    # V1 already has a qualified display projection; do not change its method.
    if row["preparation"]["version"] == "smako-edible-input-v1":
        return row, []
    basis = batch_basis(original)
    merged, redirects = [], {}
    for step in design["steps"]:
        if step["text"] == WAIT:
            previous = merged[-1]
            if (step["depends_on"] != [previous["id"]] or step.get("parallel_group")
                    or previous.get("parallel_group") or step.get("scalable_amounts")
                    or previous["duration_minutes"] + step["duration_minutes"] > 1440):
                raise ValueError((design["base_id"], "Unsafe placeholder merge", step["id"]))
            siblings = [s for s in design["steps"] if s["id"] != step["id"] and previous["id"] in s["depends_on"]]
            if siblings:
                raise ValueError((design["base_id"], "Concurrent dependency on setup", siblings))
            previous["duration_minutes"] += step["duration_minutes"]
            previous["ingredient_keys"] = sorted(set(previous["ingredient_keys"]) | set(step["ingredient_keys"]))
            redirects[step["id"]] = previous["id"]
        else:
            step["text"] = rewrite_step(step["text"], row, step)
            merged.append(step)
    for step in merged:
        step["depends_on"] = list(dict.fromkeys(redirects.get(dep, dep) for dep in step["depends_on"]))
    for process in design.get("unmeasured_processes", []):
        process["step_id"] = redirects.get(process["step_id"], process["step_id"])
    basis["step_id"] = redirects.get(basis["step_id"], basis["step_id"])
    design["steps"] = merged
    row["instructions"] = [s["text"] for s in merged]
    if row != original:
        design["batch_scaling"] = basis
    return row, sorted(redirects.items())


def critical_path(recipe):
    ends = {}
    for s in recipe.design.steps:
        ends[s.id] = max((ends[d] for d in s.depends_on), default=0) + s.duration_minutes
    return max(ends.values())


def verify_pair(old, new, *, check_scaling=True):
    """Compare food, classification, timing and scaling for all supported portions."""
    assert old.ingredients == new.ingredients
    assert old.servings == new.servings
    assert old.design.base_id == new.design.base_id and old.design.variant_id == new.design.variant_id
    # Temperatures, amounts and all other numeric instructions survive. The
    # only numeric rewrites are the explicitly reviewed equivalent thaw times.
    def numbers(texts):
        text = " ".join(texts).replace("12 timmar", "720 minuter").replace("24 timmar", "1440 minuter")
        return Counter(re.findall(r"\d+(?:[,.]\d+)?", text))
    assert numbers(old.instructions) == numbers(new.instructions), (identity(old), "numeric instruction")
    for field in ("base_id", "variant_id", "cuisines", "family", "primary_ingredient", "method", "side", "flavor_profile",
                  "components", "estimated_minutes", "active_minutes", "waiting_minutes", "total_minutes", "equipment",
                  "vegetarian", "fish", "ingredient_count", "meal_types", "dinner_level", "servings_multiple"):
        assert getattr(old.design, field) == getattr(new.design, field), (identity(old), field)
    assert old.preparation.version == new.preparation.version
    assert old.preparation.input_forms == new.preparation.input_forms
    assert old.design.unmeasured_processes == new.design.unmeasured_processes
    if not check_scaling:
        return
    for servings in range(1, 13):
        if not supports_servings(old, servings):
            continue
        before, after = _scaled(old, servings), _scaled(new, servings)
        assert before.ingredients == after.ingredients
        assert before.design.components == after.design.components
        for field in ("estimated_minutes", "total_minutes", "active_minutes", "waiting_minutes"):
            assert getattr(before.design, field) == getattr(after.design, field), (identity(old), servings, field)
        assert critical_path(before) == critical_path(after), (identity(old), servings, "critical_path")
        assert Counter(token for s in before.design.steps for token in s.scalable_amounts or ()) == Counter(
            token for s in after.design.steps for token in s.scalable_amounts or ())
        for step in before.design.steps:
            for token, _ in step.scalable_amounts or ():
                # The native exact water token and its quantity remain in one step.
                assert any(token in s.text for s in new.design.steps)


def prepare():
    if (REPORT / "library-transition.json").exists():
        raise ValueError("Already published; use --verify")
    WORK.mkdir(parents=True, exist_ok=True)
    REPORT.mkdir(parents=True, exist_ok=True)
    manifest = manifest_entries()
    overrides = json.loads((REPORT / "recipe-names.json").read_bytes())
    issued = load_entries([*manifest["current"], *manifest["history"]])
    latest = {}
    for recipe in issued:
        key = recipe.design.base_id, recipe.design.variant_id
        latest[key] = max(latest.get(key, (0, 0, 0)), tuple(map(int, recipe.design.version.split("."))))
    changed, originals, records = [], {}, []
    for recipe in current_recipes():
        old = recipe.model_dump(mode="json")
        row, merged = rewrite_recipe(old, overrides)
        if row == old:
            continue
        major, minor, patch = latest[recipe.design.base_id, recipe.design.variant_id]
        row["design"]["version"] = f"{major}.{minor}.{patch + 1}"
        row["design"]["provenance"]["reviewed_at"] = "2026-11-02"
        row["design"]["provenance"]["notes"] += " Språkgranskning 2026-11-02: mängder, råvaruformer, temperaturer och beräkningstider bevarade. Inte provlagad."
        for key in ("pack_id", "proposal_id", "sha256"):
            row["design"]["content_source"].pop(key, None)
        changed.append(row)
        originals[recipe.design.base_id, recipe.design.variant_id] = recipe
        records.append({"previous_id": identity(recipe), "previous_content_sha256": recipe.design.content_sha256,
                        "name_before": old["name"], "name_after": row["name"], "merged_wait_steps": merged,
                        "steps_before": old["instructions"], "steps_after": row["instructions"]})
    published, drafts = [], []
    for offset in range(0, len(changed), 200):
        number = offset // 200 + 1
        payload = {"schema_version": "smako-meal-pack-v1", "pack_id": f"recipe-language-20261102-{number:02}",
                   "recipes": changed[offset:offset + 200]}
        source = encoded(payload)
        validated = validate_pack_bytes(source)
        if validated["rejections"]:
            raise ValueError(validated["rejections"][:5])
        for recipe in validated["recipes"]:
            verify_pair(originals[recipe.design.base_id, recipe.design.variant_id], recipe)
            published.append(recipe)
        path = WORK / f"pack-{number:02}.json"
        path.write_bytes(source)
        drafts.append({"file": path.name, "sha256": hashlib.sha256(source).hexdigest()})
        print(f"Validated pack {number}: {len(validated['recipes'])} recipes", flush=True)
    for record, recipe in zip(records, published, strict=True):
        record.update(runtime_id=identity(recipe), content_sha256=recipe.design.content_sha256)
    review = {"before_manifest": manifest, "before_manifest_file_sha256": sha(manifest),
              "active_variants": len(current_recipes()), "changed_variants": len(records),
              "checked_servings": list(range(1, 13)), "drafts": drafts, "corrected": records,
              "cooking_test": "not_cooked", "purchase_qualification": "unchanged inputs; no new live basket claim"}
    (REPORT / "recipe-review.json").write_bytes(encoded(review))
    print(json.dumps({"changed": len(records), "merged_wait_steps": sum(len(r["merged_wait_steps"]) for r in records)}, ensure_ascii=False))


def publish():
    review = json.loads((REPORT / "recipe-review.json").read_bytes())
    if manifest_entries() != review["before_manifest"]:
        raise ValueError("Manifest changed after review")
    receipts = []
    for draft in review["drafts"]:
        path = WORK / draft["file"]
        if path.parent != WORK or hashlib.sha256(path.read_bytes()).hexdigest() != draft["sha256"]:
            raise ValueError("Draft changed after review")
    for draft in review["drafts"]:
        path = WORK / draft["file"]
        receipts.append(import_pack(path))
    after = manifest_entries()
    review["corrected"] = [{k: v for k, v in row.items() if k not in {"steps_before", "steps_after"}}
                           for row in review["corrected"]]
    review.update(after_manifest=after, after_manifest_file_sha256=sha(after),
                  added_entries=after["current"][len(review["before_manifest"]["current"]):],
                  import_receipts=receipts)
    (REPORT / "library-transition.json").write_bytes(encoded(review))
    verify()


def checked_transition(review, *, check_scaling=False):
    """Validate the complete change before applying any subset to coverage IDs."""
    before, after = review["before_manifest"], review["after_manifest"]
    assert after == {**before, "current": before["current"] + review["added_entries"]}
    assert sha(before) == review["before_manifest_file_sha256"]
    assert sha(after) == review["after_manifest_file_sha256"]
    old = {identity(r): r for r in load_entries([*before["current"], *before["history"]])}
    added = {identity(r): r for r in load_entries(review["added_entries"])}
    assert not set(old) & set(added)
    assert set(added) == {r["runtime_id"] for r in review["corrected"]}
    assert len(added) == len(review["corrected"]) == review["changed_variants"]
    assert len({r["previous_id"] for r in review["corrected"]}) == len(added)
    overrides = json.loads((REPORT / "recipe-names.json").read_bytes())
    def active_ids(recipes):
        active = {}
        for recipe in recipes:
            if identity(recipe) in before.get("revocations", {}):
                continue
            key = recipe.design.base_id, recipe.design.variant_id
            version = tuple(map(int, recipe.design.version.split(".")))
            if key not in active or version > active[key][0]:
                active[key] = (version, identity(recipe))
        return {key: value[1] for key, value in active.items()}
    before_active = active_ids(load_entries(before["current"]))
    after_active = active_ids(load_entries(after["current"]))
    assert set(before_active) == set(after_active)
    assert len(before_active) == review["active_variants"]
    for row in review["corrected"]:
        original, successor = old[row["previous_id"]], added[row["runtime_id"]]
        assert original.design.content_sha256 == row["previous_content_sha256"]
        assert successor.design.content_sha256 == row["content_sha256"]
        key = original.design.base_id, original.design.variant_id
        assert before_active[key] == identity(original) and after_active[key] == identity(successor)
        expected, merged = rewrite_recipe(original.model_dump(mode="json"), overrides)
        assert successor.name == expected["name"]
        assert successor.instructions == expected["instructions"]
        assert [s.model_dump(mode="json") for s in successor.design.steps] == expected["design"]["steps"]
        assert successor.design.batch_scaling.model_dump(mode="json") == expected["design"]["batch_scaling"]
        assert [list(pair) for pair in merged] == row["merged_wait_steps"]
        verify_pair(original, successor, check_scaling=check_scaling)
    return review


def verify():
    review = checked_transition(json.loads((REPORT / "library-transition.json").read_bytes()), check_scaling=True)
    old = load_entries([*review["before_manifest"]["current"], *review["before_manifest"]["history"]])
    added = load_entries(review["added_entries"])
    print(json.dumps({"verified_successors": len(added), "preserved_issued_versions": len(old),
                      "active_variants": review["active_variants"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--publish", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        prepare()
    elif args.publish:
        publish()
    else:
        verify()
