"""Compact source for the protein dinners batch (owner request 2026-11-25).

Each recipe is written as plain data and expanded to smako-recipe-authoring-v1:
ingredient specs "name|form|quantity|role[|=Label][|req:key]" with
form r/s/d/c/p and role P/S/V/X/F/C. Main ingredients get a reviewed range,
starchy sides a smaller range, and seasonings and fat in the main
ingredient's component follow it (not milk, cream, flour, egg or binders).
"""

FORMS = {"r": "raw_edible", "s": "as_sold", "d": "dry", "c": "cooked_drained", "p": "preserved_drained"}
ROLES = {"P": "primary", "S": "side", "V": "vegetable", "X": "sauce", "F": "flavour", "C": "cooking"}
REQ = {
    "thigh": ["pack:chicken_thigh"],
    "breast": ["pack:chicken_breast"],
    "braise": ["pack:beef_braising_cut", "pack:intake_all_10d1e6ea4dc5"],
    "quick": ["pack:beef_quick_cut", "pack:intake_all_10d1e6ea4dc5"],
    "strips": ["pack:beef_lean_strips_cut", "pack:intake_all_10d1e6ea4dc5"],
    "lamb_braise": ["pack:intake_all_f5b22d7b2487", "pack:lamb_braising_cut"],
    "lamb_quick": ["pack:intake_all_f5b22d7b2487", "pack:lamb_quick_cut"],
    "cod": ["pack:cod"],
    "salmon": ["pack:salmon"],
}
SIDES = {"potatis", "ris", "pasta", "bulgur", "couscous", "nudlar", "breda risnudlar", "risottoris", "polenta",
         "gnocchi", "majstortillas", "tortillas", "sötpotatis", "matvete", "kornris", "risvermicelli",
         "glasnudlar", "sushiris", "korngryn", "majsgryn"}
NO_FOLLOW = {"mjölk", "grädde", "vetemjöl", "mannagryn", "potatismjöl", "majsstärkelse", "havregrädde",
             "ströbröd", "ägg", "äggula", "äggvita", "kokosmjölk", "crème fraiche", "yoghurt naturell",
             "krossade tomater", "kikärtsmjöl", "rismjöl", "majsmjöl", "ost", "parmesan"}
LABELS = {"kyckling:thigh": "Kycklinglårfilé", "kyckling:breast": "Kycklingbröstfilé",
          "nötkött:braise": "Högrev eller grytbitar av nöt", "nötkött:quick": "Nötkött för stekning, t.ex. ryggbiff",
          "nötkött:strips": "Nötkött i strimlor", "fisk:cod": "Torskfilé", "fisk": "Vit fiskfilé, t.ex. sej eller torsk"}


def _step_for(q, unit):
    if unit == "st":
        return 1.0
    for s in (50, 20, 10, 5, 1):
        if q % s == 0 and q / s >= 4:
            return float(s)
    return 1.0


def _range(q, unit, low, high):
    s = _step_for(q, unit)
    down = int((low * q) // s)
    up = int((high * q) // s)
    if down == 0 and up == 0:
        return None
    lo, hi = q - down * s, q + up * s
    if lo <= 0:
        lo = q
    if lo == hi:
        return None
    return [lo, hi], s


def ing(spec):
    parts = spec.split("|")
    name, form, qty, role = parts[0], FORMS[parts[1]], float(parts[2]), ROLES[parts[3]]
    out = {"name": name, "form": form, "quantity": qty, "role": role}
    label = None
    req_key = None
    for extra in parts[4:]:
        if extra.startswith("="):
            label = extra[1:]
        elif extra.startswith("req:"):
            req_key = extra[4:]
            out["requirements"] = REQ[req_key]
        elif extra.startswith("unit:"):
            out["unit"] = extra[5:]
    out["label"] = label or LABELS.get(f"{name}:{req_key}") or LABELS.get(name) or name[:1].upper() + name[1:]
    return out


def recipe(base, name, cuisine, family, primary, method, side, flavor, equipment, comps, steps,
           servings=4, level=None, notes=None):
    components = []
    main_by_comp = {}
    for n, (cname, specs) in enumerate(comps, 1):
        items = [ing(s) for s in specs]
        for item in items:
            unit = item.get("unit", "st" if item["name"] == "ägg" and item["form"] == "as_sold" else "g")
            if item["role"] == "primary":
                r = _range(item["quantity"], unit, 0.2, 0.5)
                if r:
                    item["range"], item["step"] = r
                    main_by_comp.setdefault(n, item["name"])
            elif item["role"] == "side" and item["name"] in SIDES:
                r = _range(item["quantity"], unit, 0.3, 0.2)
                if r:
                    item["range"], item["step"] = r
        components.append({"id": f"c{n}", "name": cname, "ingredients": items})
    for n, comp in enumerate(components, 1):
        main = main_by_comp.get(n)
        if not main:
            continue
        for item in comp["ingredients"]:
            if item["role"] in ("flavour", "cooking") and item["name"] not in NO_FOLLOW:
                item["follows"] = main
    out_steps = []
    for st in steps:
        text, uses, minutes = st[0], st[1], st[2]
        after = st[3] if len(st) > 3 else None
        passive = st[4] if len(st) > 4 else False
        row = {"text": text, "uses": [u.strip() for u in uses.split(",") if u.strip()], "minutes": minutes}
        if after:
            row["after"] = list(after)
        if passive:
            row["passive"] = True
        out_steps.append(row)
    method = {"braise": "pot", "simmer": "pot", "boil": "pot", "steam": "pot", "wok": "pan", "grill": "pan"}.get(method, method)
    row = {"base_id": f"smako-{cuisine}-{base}", "name": name, "servings": servings, "meal_type": "dinner",
           "cuisine": cuisine, "family": family, "primary": primary, "method": method, "side": side,
           "flavor": flavor, "equipment": equipment, "components": components, "steps": out_steps}
    if level:
        row["level"] = level
    if notes:
        row["notes"] = notes
    return row


def pack(pack_id, recipes):
    return {"schema_version": "smako-recipe-authoring-v1", "pack_id": pack_id, "recipes": recipes}
