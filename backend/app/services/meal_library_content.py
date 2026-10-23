"""Safe Git content packs and atomic, hash-bound library publication.

The manifest is data. No recipe-specific Python registration, prices, nutrient
declarations, executable plugins or user-selected file paths are accepted.
"""
from __future__ import annotations

import hashlib
import json
import os
from functools import lru_cache
from pathlib import Path

from app.models.recipe import Recipe, RecipeIngredient, RecipePreparation
from pydantic import ValidationError

SCHEMA = "smako-meal-pack-v1"
MANIFEST_SCHEMA = "smako-recipe-library-v1"
ROOT = Path(__file__).parents[1] / "data/recipes"
MANIFEST = ROOT / "library-manifest.json"
MAX_BYTES = 16 * 1024 * 1024
MAX_RECIPES = 4096
METHODS = frozenset({"pot", "pan", "oven", "bake", "salad", "cold_assembly", "refrigerated_assembly"})


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    if path.stat().st_size > MAX_BYTES:
        raise ValueError(f"{path.name}: filen överstiger {MAX_BYTES} byte")
    return json.loads(path.read_bytes(), object_pairs_hook=_unique_pairs)


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Dubblerat JSON-fält: {key}")
        result[key] = value
    return result


def identity(recipe):
    d = recipe.design
    return f"{d.base_id}:{d.version}:{d.variant_id}"


def checked_path(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError("Manifestfilen måste ligga inom receptbiblioteket")
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path.suffix != ".json":
        raise ValueError("Manifestfilen lämnar receptbiblioteket")
    return path


def manifest_entries(root=ROOT):
    manifest = read_json(root / MANIFEST.name)
    if (set(manifest) not in ({"schema_version", "current", "history"},
                              {"schema_version", "current", "history", "revocations"})
            or manifest["schema_version"] != MANIFEST_SCHEMA):
        raise ValueError("Okänd eller felaktig biblioteksschema")
    if len(manifest["current"]) + len(manifest["history"]) > 128:
        raise ValueError("Biblioteket har för många paketgenerationer")
    revoked = manifest.get("revocations", {})
    if (not isinstance(revoked, dict) or len(revoked) > MAX_RECIPES
            or any(not isinstance(key, str) or len(key) > 300
                   or not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000
                   for key, reason in revoked.items())):
        raise ValueError("Felaktiga återkallade receptversioner")
    return manifest


@lru_cache(maxsize=1024)
def _entry_recipes(root, file, sha256):
    """Validated recipes of one content-addressed pack (immutable for its hash)."""
    path = checked_path(Path(root), file)
    raw = path.read_bytes()
    if len(raw) > MAX_BYTES or digest(raw) != sha256:
        raise ValueError(f"{file}: kontrollsumman avviker")
    pack = json.loads(raw, object_pairs_hook=_unique_pairs)
    if len(pack["recipes"]) > MAX_RECIPES:
        raise ValueError("Paketet har för många recept")
    return tuple(Recipe.model_validate(row) for row in pack["recipes"])


def load_entries(entries, root=ROOT):
    # Every planning request reads the whole library (generations and current
    # versions). A pack is verified and parsed once per exact file and hash;
    # the frozen recipes are shared, as the registered library already is.
    recipes = {}
    for entry in entries:
        if set(entry) != {"file", "sha256"}:
            raise ValueError("Felaktig manifestpost")
        for recipe in _entry_recipes(str(Path(root).resolve()), entry["file"], entry["sha256"]):
            key = identity(recipe)
            if key in recipes and recipes[key] is not recipe and recipes[key].model_dump() != recipe.model_dump():
                raise ValueError(f"{entry['file']}: motstridigt innehåll för {key}")
            recipes[key] = recipe
    return tuple(recipes.values())


def library_signature(root=ROOT):
    manifest = manifest_entries(root)
    return digest(encoded(manifest))


def _reject_unknown(raw, model, path):
    unknown = set(raw) - set(model.model_fields)
    if unknown:
        raise ValueError(f"{path}.{min(unknown)}: fältet stöds inte")


def validate_pack(path):
    """Return every rejection, never silently discard a malformed recipe."""
    if path.stat().st_size > MAX_BYTES:
        raise ValueError(f"{path}: filen överstiger {MAX_BYTES} byte")
    return validate_pack_bytes(path.read_bytes(), label=str(path))


def validate_pack_bytes(source, *, label="content pack"):
    """Shared validation for authored packs and offline expanded variants."""
    from app.services.ingredient_normalizer import canonicalize_ingredient_name
    from app.services.recipe_library import _structural_check, content_hash

    path = label
    if len(source) > MAX_BYTES:
        raise ValueError(f"{path}: filen överstiger {MAX_BYTES} byte")
    raw = json.loads(source, object_pairs_hook=_unique_pairs)
    source_sha256 = digest(source)
    if set(raw) != {"schema_version", "pack_id", "recipes"} or raw["schema_version"] != SCHEMA:
        raise ValueError(f"{path}: okänd paketstruktur")
    if not isinstance(raw["pack_id"], str) or not raw["pack_id"] or len(raw["pack_id"]) > 100:
        raise ValueError(f"{path}: ogiltigt pack_id")
    if not isinstance(raw["recipes"], list) or not 1 <= len(raw["recipes"]) <= MAX_RECIPES:
        raise ValueError(f"{path}: ogiltigt receptantal")
    recipes, errors, seen = [], [], {}
    for index, row in enumerate(raw["recipes"]):
        ref = f"recipes[{index}]"
        design = row.get("design") if isinstance(row, dict) else None
        key = design.get("base_id", "unknown") if isinstance(design, dict) else "unknown"
        try:
            _reject_unknown(row, Recipe, ref)
            for n, ingredient in enumerate(row["ingredients"]):
                _reject_unknown(ingredient, RecipeIngredient, f"{ref}.ingredients[{n}]")
                if canonicalize_ingredient_name(ingredient["name"]) != ingredient["canonical_name"]:
                    raise ValueError(f"{ref}.ingredients[{n}].canonical_name: identiteten avviker")
            data = json.loads(json.dumps(row))
            data["design"]["content_sha256"] = "0" * 64
            inherited = data["design"].get("content_source")
            if inherited and "pack_id" not in inherited:
                # A new version may carry reviewed safety/storage/method notes
                # forward; it is still bound to this pack and source file.
                data["design"]["content_source"] = {
                    "priority": 1, "timing_basis": "authored_estimate_coarse_dependencies",
                    "active_minutes": data["design"]["active_minutes"], **inherited,
                    "pack_id": raw["pack_id"], "proposal_id": key, "sha256": source_sha256}
            if not data["design"].get("content_source"):
                data["design"]["content_source"] = {
                    "pack_id":raw["pack_id"],"proposal_id":key,"sha256":source_sha256,
                    "priority":1,"timing_basis":"authored_estimate_coarse_dependencies",
                    "active_minutes":data["design"]["active_minutes"],
                    "method_note":"Summera använda ätbara insatsers deklarationer eller uttryckligt tillåtna referenser per portion. Ingen retention, densitet, avrunnen andel eller tillagad vikt antas.",
                    "scaling_note":"Mängder skalas med portionsantal; extra beredningstid och eventuella omgångar visas separat.",
                    "safety_sources":[],
                    "storage_note":"Följ förpackningens hanterings- och hållbarhetsanvisning. Ingen veckohållbarhet för tillagad mat eller öppnade produkter har verifierats.",
                }
            data.pop("preparation", None)
            recipe = Recipe.model_validate(data)
            d = recipe.design
            if not d or d.method not in METHODS:
                raise ValueError(f"{ref}.design.method: beredningsmetoden stöds inte")
            if not d.meal_types or len(set(d.meal_types)) != len(d.meal_types):
                raise ValueError(f"{ref}.design.meal_types: ogiltig måltidsfördelning")
            if d.active_minutes is None or d.total_minutes is None:
                raise ValueError(f"{ref}.design: aktiv tid och total tid krävs")
            if d.total_minutes < d.active_minutes + d.waiting_minutes:
                raise ValueError(f"{ref}.design.total_minutes: understiger aktiv tid och väntan")
            if not all(c.amounts for c in d.components):
                raise ValueError(f"{ref}.design.components: komponentmängder krävs")
            if d.method in {"cold_assembly", "refrigerated_assembly", "salad"} and any(
                    i.canonical_name in {"kyckling", "nötfärs", "fläskkött", "ägg", "fisk", "lax"}
                    and i.form == "raw_edible" for i in recipe.ingredients):
                raise ValueError(f"{ref}.design.method: rå animalisk ingrediens kräver varm metod")
            sha = content_hash(recipe)
            recipe = recipe.model_copy(update={"design": d.model_copy(update={"content_sha256": sha}),
                "preparation": RecipePreparation(version="smako-authored-input-v2",
                    origin="smako_recipe_design", parent_sha256=sha, family=d.family,
                    input_forms={i.canonical_name:i.form for i in recipe.ingredients})})
            _structural_check(recipe)
            key = identity(recipe)
            if key in seen and seen[key] != sha:
                raise ValueError(f"{ref}: samma ID/version har olika innehåll")
            seen[key] = sha
            recipes.append(recipe)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            field = ref
            if isinstance(exc, ValidationError):
                field += "." + ".".join(str(x) for x in exc.errors()[0]["loc"])
            errors.append({"file": str(path), "field": field, "recipe_id": key, "reason": str(exc)})
    return {"pack_id":raw["pack_id"], "source_sha256":source_sha256,
            "recipes":recipes, "rejections":errors}


def pack_diff(validated, root=ROOT):
    m = manifest_entries(root)
    previous = {identity(r):r for r in load_entries([*m["current"], *m["history"]],root)}
    bases = {r.design.base_id for r in previous.values()}
    rows, seen = [], set()
    for recipe in validated["recipes"]:
        key = identity(recipe)
        status = ("unchanged" if key in previous and previous[key].model_dump() == recipe.model_dump()
                  else "conflict" if key in previous else "duplicate" if key in seen
                  else "new_version" if any(r.design.base_id == recipe.design.base_id and r.design.variant_id == recipe.design.variant_id for r in previous.values())
                  else "new_variant" if recipe.design.base_id in bases else "new_recipe")
        rows.append({"id":key,"status":status})
        seen.add(key)
    return rows


def atomic_write(path, data):
    temporary = path.with_name(path.name + ".next-" + os.urandom(8).hex())
    with temporary.open("xb") as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary, path)


def revoke_recipe(recipe_id, reason, *, root=ROOT):
    """Withdraw planning approval while retaining immutable issued content."""
    manifest = manifest_entries(root)
    if recipe_id not in {identity(r) for r in load_entries(
            [*manifest["current"], *manifest["history"]], root)}:
        raise ValueError("Återkallelsen avser en okänd receptversion")
    if not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000:
        raise ValueError("Återkallelsen måste ha en konkret orsak")
    revoked = manifest.setdefault("revocations", {})
    if recipe_id in revoked and revoked[recipe_id] != reason:
        raise ValueError("Befintlig återkallelse har en annan orsak")
    revoked[recipe_id] = reason
    atomic_write(root / MANIFEST.name, encoded(manifest))
    if root.resolve() == ROOT.resolve():
        from app.services.recipe_library import reset_library_caches
        reset_library_caches()
    return {"revoked_id": recipe_id, "reason": reason,
            "manifest_sha256": library_signature(root), "issued_content_preserved": True}


def import_pack(path, *, root=ROOT, accepted_ids=None):
    validated = validate_pack(path)
    diff = pack_diff(validated,root)
    if any(row["status"] == "conflict" for row in diff):
        raise ValueError("Importkonflikt: samma ID/version har annat innehåll")
    if validated["rejections"] and accepted_ids is None:
        raise ValueError("Paketet har avvisningar; godkänn en uttrycklig delmängd")
    recipes = [r for r in validated["recipes"] if accepted_ids is None or identity(r) in accepted_ids]
    if accepted_ids is not None and set(accepted_ids) != {identity(r) for r in recipes}:
        raise ValueError("Den godkända delmängden innehåller okända eller avvisade ID:n")
    if not recipes:
        raise ValueError("Ingen giltig godkänd delmängd")
    content = encoded({"library_version":SCHEMA, "recipes":[r.model_dump(mode="json") for r in recipes]})
    if len(content) > MAX_BYTES:
        # load_entries rejects a larger pack, so publishing it would make the
        # whole library unloadable. Nothing has been written yet.
        raise ValueError(f"Det publicerade paketet blir {len(content)} byte, mer än {MAX_BYTES}; "
                         "dela upp utkastet i flera paket")
    sha = digest(content)
    target = root / ("meal-pack-" + sha + ".json")
    if target.exists() and target.read_bytes() != content:
        raise ValueError("Befintligt paket har ändrats")
    if not target.exists():atomic_write(target,content)
    manifest = manifest_entries(root)
    entry = {"file":target.name,"sha256":sha}
    if entry not in manifest["current"]:
        manifest["current"].append(entry)
        atomic_write(root/MANIFEST.name,encoded(manifest))
    if root.resolve() == ROOT.resolve():
        from app.services.recipe_library import reset_library_caches
        reset_library_caches()
    return {"source_sha256":validated["source_sha256"],"manifest_sha256":library_signature(root),
            "rejections":validated["rejections"],"diff":diff,"published_file":target.name}
