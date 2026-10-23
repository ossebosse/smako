"""Content-bound publication predecessors; cold misses may not skip a node."""
from functools import lru_cache

from app.services.meal_library_content import identity, manifest_entries
from app.services.planner_context import content_digest
from app.services.recipe_library import current_recipes
from app.services.reference_library import reference_manifest


@lru_cache(maxsize=4)
def _publications(signature, generation):
    manifest = manifest_entries()
    entries = manifest["current"][:generation]
    pin = reference_manifest()
    base = pin["manifest"]
    if entries[:len(base["entries"])] != base["entries"]:
        return ()
    nodes, previous, predecessor = [], None, None
    for end in range(len(base["entries"]), len(entries) + 1):
        recipes = tuple((identity(r), content_digest(r)) for r in current_recipes(end))
        if previous is None and recipes != tuple(tuple(row) for row in base["recipes"]):
            return ()  # Revocation/content edit breaks the certified base.
        if previous is not None and recipes[:len(previous)] != previous:
            return ()  # A reissue is a new context, never an append-only node.
        node = {"generation": end, "count": len(recipes), "recipes": recipes,
                "predecessor": predecessor, "entries": entries[:end]}
        node["sha256"] = content_digest(node)
        nodes.append(node)
        previous, predecessor = recipes, node["sha256"]
    return tuple(nodes)


def publications(generation=None):
    manifest = manifest_entries()
    return _publications(content_digest(manifest), generation or len(manifest["current"]))


def slots_record(slots):
    return [{"slot": s.id, "recipe": content_digest(s.recipe),
             "recipe_name": s.recipe.name if s.recipe else None} for s in slots]


def index_slots(options):
    digests = {}
    lookup = {}
    for group in options:
        for slot in group:
            key = id(slot.recipe)
            if key not in digests:
                digests[key] = content_digest(slot.recipe)
            lookup[slot.id, digests[key]] = slot
    return lookup


def restore_slots(rows, options, lookup=None):
    if not isinstance(rows, list) or len(rows) != len(options):
        return None
    lookup = index_slots(options) if lookup is None else lookup
    result = []
    for row, group in zip(rows, options, strict=True):
        if (not isinstance(row, dict) or not isinstance(row.get("slot"), str)
                or not isinstance(row.get("recipe"), str)):
            return None
        found = lookup.get((row.get("slot"), row.get("recipe")))
        if found is not None and not any(slot is found for slot in group):
            return None
        if found is None:
            return None
        result.append(found)
    return result


def load_certificate_record(artifacts, context, node, predecessor):
    if artifacts is None:
        return None
    data = artifacts.load("menu_certificate", content_digest([context, node["sha256"]]))
    if not isinstance(data, dict):
        return None
    body = {k: v for k, v in data.items() if k != "sha256"}
    if (data.get("sha256") != content_digest(body) or body.get("context") != context
            or body.get("publication") != node["sha256"]
            or body.get("predecessor") != predecessor or body.get("policy") != "smako-verified-reference-v1"
            or body.get("replay_complete") is not True
            or not isinstance(body.get("audit"), dict) or not body["audit"].get("passed")):
        return None
    from decimal import Decimal, DecimalException
    try:
        if not isinstance(body.get("total"), str) or not Decimal(body["total"]).is_finite() or Decimal(body["total"]) < 0:
            return None
    except (DecimalException, TypeError, ValueError):
        return None
    return data


def load_certificate(artifacts, context, node, options, predecessor, lookup=None):
    data = load_certificate_record(artifacts, context, node, predecessor)
    if data is None:
        return None
    body = data
    winner = restore_slots(body.get("winner"), options, lookup)
    reference = restore_slots(body.get("reference"), options, lookup)
    allowed = {row[0] for row in node["recipes"]}
    if winner is not None and reference is not None and any(
            slot.recipe and slot.recipe.design and identity(slot.recipe) not in allowed
            for slot in (*winner, *reference)):
        return None
    return (winner, reference, data) if winner is not None and reference is not None else None


def save_certificate(artifacts, context, node, predecessor, winner, reference, result, *, replay_complete=True,
                     qualification=(), candidate_inputs=None, qualification_library=None, culinary_profiles=None):
    from app.services.basket_calculator import money

    body = {"context": context, "publication": node["sha256"], "predecessor": predecessor,
            "policy": "smako-verified-reference-v1", "winner": slots_record(winner),
            "reference": slots_record(reference), "total": str(money(result["basket"].total)),
            "replay_complete": replay_complete,
            "audit": result["audit"].model_dump(mode="json")}
    data = {**body, "sha256": content_digest(body)}
    if artifacts is not None:
        key = content_digest([context, node["sha256"]])
        saved = artifacts.save("menu_certificate", key, data)
        if saved and node["sha256"] == qualification_library:
            artifacts.save("menu_view", key, {"certificate": data["sha256"], "candidate_inputs": candidate_inputs,
                "culinary_profiles": culinary_profiles,
                "qualification": [{k: p[k] for k in ("meal_type", "raw", "qualified") if k in p}
                                  for p in qualification]})
    return data
