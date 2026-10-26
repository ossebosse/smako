"""Reproduce explicit, narrow ingredient decisions against retained research.

Patterns select evidence for manual review, never products for checkout. Runtime
bindings below require the exact reviewed GTIN, whole label and package amount.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from app.services.ingredient_normalizer import _search_text

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "backend/app/data/ingredients/intake-all-20261026.json"

# Culinary definitions, individually reviewed against the author's ingredient
# labels. These are NOT positive product references. Until an exact, source-bound
# manufacturer declaration supplies the specified identity/form/unit, purchasing
# fails closed. In particular, net whole-fruit mass is not edible peeled mass.
DEFINITIONS = {
    "salladslök": "Ansa och väg ätliga vita och gröna delar; inte knippets bruttovikt.",
    "mynta": "Färska ätliga myntablad; inte torkad mynta eller krukans totalvikt.",
    "purjolök": "Ansa och väg ätlig purjolök utan rot och kasserade blad.",
    "tamarindpasta": "Kärnfri osötad tamarindpasta; inte sötad sås eller koncentrat med annan spädning.",
    "pumpa": "Rått ätligt pumpakött utan skal, kärnor och trådigt inre.",
    "päron": "Ätligt päronkött utan kärnhus och stjälk.",
    "masa harina": "Nixtamaliserat torkat majsmjöl till masa; inte vanligt majsmjöl, stärkelse eller polenta.",
    "fänkål": "Ansad ätlig fänkål; borttagna delar ingår inte i receptvikten.",
    "mozzarella": "Naturell mozzarella; avrunnen form kräver deklarerad avrunnen mängd, as_sold kräver ost utan lag.",
    "apelsin": "Ätligt apelsinkött utan skal och kärnor; inte juice eller hel fruktvikt.",
    "citrongräs": "Ansad färsk ätlig mjuk del; inte torkat pulver eller hela träiga stjälkars vikt.",
    "pärlkorn": "Torra polerade hela korn; inte korngryn, matvete eller kokt spannmål.",
    "klibbigt ris": "Torrt glutinöst klibbigt ris; inte vanligt jasminris eller sushiris.",
    "rotselleri": "Skalad rå ätlig rotselleri.",
    "rädisa": "Ansade råa rädisor utan blast och rotspets.",
    "bambuskott": "Konserverade bambuskott; använd deklarerad avrunnen vikt utan lag.",
    "banan": "Ätligt rått banankött utan skal.",
    "räkor": "Kokta skalade avrunna räkor; skal och lag får inte ingå i receptvikten.",
    "tapiokastärkelse": "Torr ren tapiokastärkelse; inte pärlor eller annan stärkelse.",
    "pak choi": "Ansade råa ätliga blad och stjälkar av pak choi.",
    "sallad": "Råa ansade ätliga salladsblad; inte rotklump, dressing eller färdig salladsrätt.",
    "äggula": "Rå separerad ätlig äggula; köp kräver deklarerad mängd gula, inte hela äggs massa.",
    "äggvita": "Rå separerad ätlig äggvita; köp kräver deklarerad mängd vita, inte hela äggs massa.",
    "rimmat fläsk": "Rått rimmat benfritt fläsk; inte rökt eller färdigstekt bacon.",
    "gelatinblad": "Livsmedelsgelatin i blad med deklarerad gramvikt; inte vegetarisk gelbildare.",
    "klibbigt rismjöl": "Torrt mjöl av glutinöst ris; inte vanligt rismjöl.",
    "tapiokapärlor": "Torra tapiokapärlor av receptets lilla pärltyp; inte färdigkokt boba eller stärkelsepulver.",
    "breda risnudlar": "Torra breda risnudlar; inte äggnudlar eller tunna risvermicelli.",
    "kronärtskocka": "Konserverade ätliga kronärtskockshjärtan; deklarerad avrunnen vikt utan lag.",
    "kålrot": "Skalad rå ätlig kålrot.",
    "makrill": "Rå benfri ätlig makrillfilé; inte hel fisk, rökt fisk eller tomatkonserv.",
    "rispapper": "Ätliga rispappersark; dry avser torra ark, as_sold avser samma köpta ark utan blötläggningsvatten.",
    "sardiner": "Konserverade sardiner med deklarerad avrunnen ätlig fiskmängd utan sås/olja.",
    "uradlinser": "Torr skalad urad dal (Vigna mungo); inte mungbönor, belugalinser eller chana dal.",
    "vinblad": "Konserverade ätliga vinblad; deklarerad avrunnen mängd, inte fyllda dolmar.",
    "bittergurka": "Rått ansat ätligt fruktkött av bittergurka utan kärnor.",
    "chana dal": "Torra delade skalade kikärtor av chana dal-typ; inte vanligt kikärtsmjöl eller hela kokta kikärtor.",
    "gröna mungbönor": "Kokta avrunna gröna mungbönor; torra bönor kräver separat författad tillagningskedja.",
    "palsternacka": "Skalad rå ätlig palsternacka.",
    "plommon": "Rått ätligt plommonkött utan kärnor och stjälk.",
    "surkål": "Fermenterad vitkål med deklarerad avrunnen vikt; inte färdig rätt eller enbart burkens nettovikt.",
    "vattenkastanjer": "Konserverade skalade vattenkastanjer med deklarerad avrunnen vikt.",
    "silkestofu": "Naturell silkestofu; inte fast tofu eller tofu med sås.",
    "kefir": "Naturell osötad kefir med deklarerad ml-volym; ingen fri massa-till-volym-omräkning.",
    "varmrökt lax": "Ätlig benfri varmrökt lax utan skinn; inte kallrökt eller rå lax.",
    "bläckfisk": "Rå rensad ätlig bläckfisk utan inälvor och hårda delar.",
    "fjälster": "Livsmedelsgodkänt ätligt fjälster med deklarerad avrunnen gramvikt; inte metervara omräknad utan belägg.",
    "fläsklever": "Rå putsad ätlig fläsklever.",
    "fläsksida med svål": "Rå benfri fläsksida med ätlig svål; inte benmassa eller färdigkokt kött.",
    "groddade mungbönor": "Ätliga groddade mungbönor med deklarerad köpmängd; inte torra bönor eller annan grodd.",
    "gröna linser": "Kokta avrunna gröna linser i denna form; inte torr linsmassa.",
    "kaffe": "Bryggt osötat kaffe, deklarerad ml-volym; inte torra kaffebönor, pulver eller massa omräknad till volym.",
    "kalvlägg med ben": "Rå kalvlägg med ben, as_sold inköpsvikt inklusive ben. Ätlig näringsmängd saknar stödd benavskiljning.",
    "kokta ägg": "Kokta skalade ätliga ägg med deklarerad gramvikt; inte skaläggs bruttomassa.",
    "mangold": "Ansade råa ätliga mangoldblad och stjälkar.",
    "matbanan": "Skalat ätligt matbanankött av mognad angiven i receptet; inte vanlig dessertbanan.",
    "matjessill": "Ätlig matjessillfilé med deklarerad avrunnen vikt utan lag.",
    "mungbönsstärkelse": "Ren torr mungbönsstärkelse; inte mungbönsmjöl eller glasnudlar.",
    "musslor": "as_sold avser levande musslor inklusive skal; cooked_drained avser enbart kokt avrunnet musselkött. Ingen antagen skalandel.",
    "pomelo": "Rått ätligt pomelokött utan skal, hinnor och kärnor.",
    "risvermicelli": "Torra tunna risvermicelli; inte mungbönsglasnudlar eller breda risnudlar.",
    "runda risnudlar": "Torra runda risnudlar; inte vete-/äggnudlar eller platta risnudlar.",
    "råa räkor": "Råa skalade ätliga räkor utan skal; inte kokta räkor eller skalvikt.",
    "sattu": "Torrt mjöl av rostade kikärtor; inte rått kikärtsmjöl eller vetemjöl.",
    "svart te": "Torra svarta teblad utan smaksättning; inte färdig tedryck eller tepåsens förpackningsmassa.",
    "svarta linser": "Kokta avrunna svarta linser; inte urad dal eller torr linsmassa.",
    "vegansk smördeg": "Smördeg vars fullständiga produktdeklaration styrker vegansk sammansättning; vanlig smördeg är inte automatiskt vegansk.",
    "vetegluten": "Torrt vitalt vetegluten för seitan; inte vetemjöl eller färdig seitan.",
    "apelsinskal": "Ätligt tvättat finrivet yttre apelsinskal utan det vita; separat deklarerad mängd skal, inte hel apelsinvikt.",
    "edamame i balja": "Edamame inklusive oätlig balja, as_sold inköpsvikt. Ätlig näringsmängd kräver separat belagd bönandel.",
    "filmjölk": "Naturell osötad filmjölk med deklarerad ml-volym, inte antagen ml=g.",
    "grapefrukt": "Rått ätligt grapefruktkött utan skal, hinnor och kärnor.",
    "grön matbanan": "Grön omogen matbanan, skalat ätligt fruktkött; inte mogen matbanan eller dessertbanan.",
    "hirs": "Torra skalade hirsgryn; inte färdigkokt hirs eller fågelfoder.",
    "kastanjer": "Kokta skalade ätliga kastanjer med deklarerad avrunnen mängd; inte hästkastanj eller hel nöt med skal.",
    "kokosolja": "Ren ätlig kokosolja med deklarerad gramvikt; inte kokosmjölk eller olja mätt i ml utan densitetsbelägg.",
    "majskolv": "Ätlig majs på kolv, as_sold inköpsvikt inklusive oätlig kolv. Ingen antagen kärnandel för näring.",
    "padrónpaprika": "Rå ansad ätlig padrónpaprika; inte annan godtycklig chili.",
    "pektin": "Livsmedelspektin i receptets angivna gramdos; inte syltsocker eller annan gelbildare.",
    "popcornmajs": "Torra rena majskärnor av popcornsort; inte mikropopcorn med tillsatser.",
    "psylliumfröskal": "Torra livsmedelsgodkända psylliumfröskal; inte hela frön eller annan fiber.",
    "risflingor": "Torra risflingor; inte puffat ris eller havregryn.",
    "rättika": "Skalad rå ätlig rättika.",
    "rökt makrill": "Ätligt benfritt rökt makrillkött utan skinn; inte hel fisk eller rå makrill.",
    "vattenmelon": "Rått ätligt vattenmelonkött utan skal och kärnor.",
    "ägg": "Kokta skalade ätliga ägg i cooked_drained; ingen omräkning från skalägg utan stödd mängdbevisning.",
}


def pending_definitions(pending):
    from app.services.meal_library_content import encoded

    source = ROOT / "backend/app/data/recipes/incoming/authoring-800-20261025"
    usages = {}
    for path in sorted((source / "paket").glob("*.json")):
        file_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        for n, recipe in enumerate(json.loads(path.read_bytes())["recipes"]):
            for component in recipe["components"]:
                for i in component["ingredients"]:
                    key = i["name"] + "|" + i["form"]
                    usages.setdefault(key, []).append({"source_file": path.relative_to(source).as_posix(),
                        "source_sha256": file_sha, "source_index": n,
                        "recipe_sha256": hashlib.sha256(encoded(recipe)).hexdigest(),
                        "label": i.get("label", ""), "unit": i["unit"]})
    result = []
    for item in pending:
        name, form = item["identity"].split("|")
        if name in {"solrosfrön", "pumpafrön"}:
            continue  # Explicit authored kernel variants in complete_intake_delivery.
        definition = DEFINITIONS[name]  # Missing review must be an error.
        evidence = usages[item["identity"]]
        units = {e["unit"] for e in evidence}
        assert len(units) == 1, (name, form, units)
        unit = units.pop()
        key = "intake_all_" + hashlib.sha256(item["identity"].encode()).hexdigest()[:12]
        result.append({"name": name, "form": form, "unit": unit, "requirements": ["pack:" + key],
            "kind": "definition_only", "definition": definition,
            "required_classification": f"culinary_input:{name}:{form}:{unit}",
            "gross_inedible_mass": form == "as_sold" and name in {"kalvlägg med ben", "edamame i balja", "musslor", "majskolv"},
            "review_basis": "Reviewed culinary definition and source quantities only. " + definition
                + " Purchasing requires an exact source-bound manufacturer culinary declaration of this identity, form and usable unit/mass; no current SKU approved. No inferred density, edible yield, drained mass or cooking conversion. Nutrition/allergens/organic unknown until separately qualified.",
            "evidence": [{"kind": "authoring_definition_review", **e} for e in evidence],
            "product_evidence_pending": item})
    return result

# Full labels, deliberately excluding flavoured/filled/composite alternatives.
DECISIONS = {
    "koriander|raw_edible": ("g", r"koriander finhackad(?: fryst)?", "frozen_edible"),
    "grönkål|raw_edible": ("g", r"(?:hackad gronkal|gronkal grovhackad)(?: fryst)?", "frozen_edible"),
    "sparris|raw_edible": ("g", r"sparris(?: fryst)?", "frozen_edible"),
    "okra|raw_edible": ("g", r"okra(?: fryst)?", "frozen_edible"),
    "lingon|as_sold": ("g", r"lingon(?: ekologiska| frysta| fryst)*", "frozen_edible"),
    "nori|as_sold": ("g", r"yaki nori sushi|sushi nori roasted seeweed", "plain"),
    "böngroddar|as_sold": ("g", r"bongroddar ekologisk", "plain"),
    "böngroddar|raw_edible": ("g", r"bongroddar ekologisk", "plain"),
    "nötkött|raw_edible": ("g", r"(?:hogrev benfri|ryggbiff|entrecote|flankstek)(?: notkott| sverige| irland| kanada| farsk| fryst)*", "estimated_boneless"),
    "lammkött|raw_edible": ("g", r"(?:lammstek benfri|lammrostbiff benfri|lammytterfile)(?: sverige| nya zeeland| farsk| fryst)*", "estimated_boneless"),
    "röd currypasta|as_sold": ("g", r"red curry paste", "mixture"),
    "gula ärtor|dry": ("g", r"gula arter", "dry"),
    "avokado|raw_edible": ("g", r"avokado (?:tarningar|skivor)(?: fryst)?", "frozen_edible"),
    "äppelcidervinäger|as_sold": ("ml", r"appelcider vinager", "mixture"),
    "grädde|as_sold": ("ml", r"vispgradde(?: 3dl| 5dl| 36| 40| laktosfri)*", "dairy"),
    "senapsfrön|dry": ("g", r"(?:gult senapsfro|senapsfro (?:brunt|gula)) pase", "dry"),
    "havregrädde|as_sold": ("ml", r"imat matlagnings(?:bas|gradde)(?: 13)?", "mixture"),
    "kokosflingor|as_sold": ("g", r"kokos riven(?: ekologisk)?", "plain"),
    "rökt lax|as_sold": ("g", r"kallrokt lax(?: skivad)?", "mixture"),
    "lammfärs|raw_edible": ("g", r"lammfars fetthalt lagre an 20", "raw_boneless"),
    "kycklinglever|raw_edible": ("g", r"kycklinglever(?: fryst| sverige)*", "raw_boneless"),
    "alkoholfri öl|as_sold": ("ml", r"heineken (?:0 0 ol alkoholfri burk|alkoholfri 0 0 ol flaska)", "mixture"),
    "edamame i balja|as_sold": ("g", r"edamame(?: bonor| sojabonor)? i balja(?: fryst| frysta)?", "mixture"),
    "gröna linser|dry": ("g", r"grona linser(?: ekologiska)?", "dry"),
    "ricotta|as_sold": ("g", r"ricotta(?: 12)?", "dairy"),
    "torrjäst|dry": ("g", r"torrjast matbrod", "dry"),
    "garam masala|dry": ("g", r"garam masala(?: burk)?", "mixture"),
    "majsgryn|dry": ("g", r"polenta majsgryn", "dry"),
    "vaniljpulver|dry": ("g", r"vaniljpulver(?: bourbon)?", "dry"),
    "mörk choklad|as_sold": ("g", r"mork choklad (?:56|70)|(?:70|85) cacao mork choklad", "mixture"),
    "bulgur|dry": ("g", r"bulgur(?: fullkorn)?", "dry"),
    "honung|as_sold": ("g", r"honung(?: ekologisk| flytande| svensk)*", "plain"),
    "jäst|as_sold": ("g", r"jast matbrod farsk", "mixture"),
    "paneer|as_sold": ("g", r"paneer cheese original(?: 8)?", "dairy"),
    "rödvinsvinäger|as_sold": ("ml", r"rodvinsvinager", "mixture"),
    "smördeg|as_sold": ("g", r"smordeg", "mixture"),
    "cashewnötter|as_sold": ("g", r"(?:naturella )?cashewnotter(?: ekologiska)?", "plain"),
    "kryddpeppar|dry": ("g", r"kryddpeppar malen(?: burk)?", "dry"),
    "halloumi|as_sold": ("g", r"halloumi(?: ekologisk)?", "dairy"),
    "filodeg|as_sold": ("g", r"(?:farsk )?filodeg(?: tunna)?", "mixture"),
    "majsmjöl|dry": ("g", r"majsmjol(?: finmalet)?", "dry"),
    "mannagryn|dry": ("g", r"mannagryn", "dry"),
    "kakao|dry": ("g", r"kakao(?: ekologisk| kakao)?", "dry"),
    "risottoris|dry": ("g", r"avorio risottoris", "dry"),
    "korngryn|dry": ("g", r"korngryn", "dry"),
    "matvete|dry": ("g", r"matvete", "dry"),
    "kardemumma|dry": ("g", r"kardemumma(?: malen| grovmalen)(?: burk)?", "dry"),
    "bikarbonat|dry": ("g", r"bikarbonat", "dry"),
    "russin|as_sold": ("g", r"russin(?: ekologiska)?", "plain"),
    "rågmjöl|dry": ("g", r"ragmjol(?: finmalt| grovt| ekologiskt)*", "dry"),
    "tahini|as_sold": ("g", r"tahini sesampasta", "mixture"),
    "florsocker|dry": ("g", r"florsocker", "mixture"),
    "hasselnötter|as_sold": ("g", r"hasselnotter(?: hela| hackade)*", "plain"),
    "muskot|dry": ("g", r"muskotnot malen(?: burk)?", "dry"),
    "sojadryck|as_sold": ("ml", r"soya no sugars sojadryck", "mixture"),
    "apelsinjuice|as_sold": ("ml", r"apelsinjuice(?: med fruktkott| utan fruktkott| farskpressad)*", "mixture"),
    "potatismjöl|dry": ("g", r"potatismjol", "dry"),
    "risvinäger|as_sold": ("ml", r"risvinager", "mixture"),
    "balsamvinäger|as_sold": ("ml", r"balsamvinager(?: aged)?", "mixture"),
    "dadlar|as_sold": ("g", r"dadlar(?: eko| ekologiska| urkarnade)*", "plain"),
    "getost|as_sold": ("g", r"(?:chevre )?getost", "dairy"),
    "havreris|dry": ("g", r"(?:svenskt )?havreris(?: svenskt)?", "dry"),
    "knäckebröd|as_sold": ("g", r"(?:brungraddat )?knackebrod(?: original| fullkorn| grovt)*", "mixture"),
    "tempeh|as_sold": ("g", r"tempeh original fast tarnad vegansk", "mixture"),
    "färskost|as_sold": ("g", r"(?:brunch )?farskost(?: naturell| original)*", "dairy"),
    "kummin|dry": ("g", r"kummin hel(?: pase)?", "dry"),
    "polenta|dry": ("g", r"polenta(?: majsgryn)?", "dry"),
    "puffat ris|as_sold": ("g", r"puffat ris|vargarda ris puffat rostat ris", "plain"),
    "torkade aprikoser|as_sold": ("g", r"aprikoser torkade", "plain"),
    "mandelmjöl|dry": ("g", r"mandelmjol(?: glutenfritt)?", "dry"),
    "varmrökt lax|as_sold": ("g", r"varmrokt lax", "mixture"),
    "blodpudding|as_sold": ("g", r"blodpudding(?: glutenfri| original skivad)*", "mixture"),
    "falukorv|as_sold": ("g", r"falukorv", "mixture"),
    "glasnudlar|dry": ("g", r"glasnudlar", "dry"),
    "kikärtor|dry": ("g", r"kikartor(?: ekologiska| eko)*", "dry"),
    "lufttorkad skinka|as_sold": ("g", r"skinka lufttorkad", "mixture"),
    "vallmofrön|dry": ("g", r"vallmofron", "dry"),
    "ädelost|as_sold": ("g", r"adelost special 45", "dairy"),
    "bovetemjöl|dry": ("g", r"bovetemjol(?: glutenfritt)?", "dry"),
    "bovete|dry": ("g", r"torkat bovete", "dry"),
    "chiafrön|dry": ("g", r"chiafron", "dry"),
    "grahamsmjöl|dry": ("g", r"grahamsmjol(?: ekologiskt| biodynamiskt)*", "dry"),
    "kokt skinka|as_sold": ("g", r"kokt skinka", "mixture"),
    "kondenserad mjölk|as_sold": ("g", r"kondenserad mjolk", "mixture"),
    "mascarpone|as_sold": ("g", r"mascarpone", "dairy"),
    "quinoa|dry": ("g", r"quinoa tricolore|rod quinoa|vit quinoa", "dry"),
    "stenbitsrom|as_sold": ("g", r"caviar rod stenbitsrom", "mixture"),
    "äppeljuice|as_sold": ("ml", r"appeljuice(?: farskpressad)?", "mixture"),
    "gräslök|raw_edible": ("g", r"graslok finhackad(?: fryst)?", "frozen_edible"),
    "mango|raw_edible": ("g", r"mango(?: tarnad| bitar| fryst)*", "frozen_edible"),
    "hallon|raw_edible": ("g", r"hallon(?: frysta| fryst)*", "frozen_edible"),
    "blåbär|raw_edible": ("g", r"blabar(?: frysta| fryst)*", "frozen_edible"),
    "jordgubbar|raw_edible": ("g", r"jordgubbar(?: frysta| fryst)*", "frozen_edible"),
    "ananas|raw_edible": ("g", r"ananas(?: bitar| fryst)*", "frozen_edible"),
}


def build(research):
    report = json.loads(research.read_bytes())
    accepted, pending = [], []
    for entry in report["identities"]:
        key = entry["identity"]
        if key not in DECISIONS:
            pending.append({"identity": key, "reason": "No reviewed whole product with the required edible/drained/form/unit basis yet",
                            "retrieved_products": entry["retrieved_products"]})
            continue
        unit, pattern, kind = DECISIONS[key]
        evidence = []
        for candidate in entry["candidates"]:
            p, f = candidate["product"], candidate["facts"]
            label = _search_text(p["name"])
            category = _search_text(p.get("category") or "")
            if not (re.fullmatch(pattern, label) and p.get("source_provenance") and p["package_unit"] == unit
                    and p["usable_unit"] == unit and p["usable_quantity"] == p["package_quantity"]
                    and p["quantity_confidence"] in ({"exact", "estimated"} if kind == "estimated_boneless" else {"exact"})
                    and p["sale_model"] in ({"fixed_package", "variable_weight_package"} if kind == "estimated_boneless" else {"fixed_package"})):
                continue
            if re.search(r"\b(?:hushall|stad|rengoring|djurfoder|hund|katt|sallskapsdjur)\b|glasspaket", category):
                continue
            composition = " ".join((f or {}).get("ingredients", [])).casefold().split("kan innehålla")[0]
            if kind == "frozen_edible" and "fryst" not in category + " " + label:
                continue
            if kind == "dry" and (re.search(r"kokt|fardigmat|konserv|fryst|tetra", category + " " + label)
                                  or "vatten" in composition):
                continue
            if kind in {"plain", "dry"} and re.search(r"\b(?:salt|socker|olja|smör|sirap|honung)\b", composition):
                continue
            if key == "kikärtor|dry" and p["package_quantity"] != 500:
                continue
            if key == "gröna linser|dry" and p["package_quantity"] not in {500, 800}:
                continue
            evidence.append({"store_id": p["store_id"], "product_id": p["product_id"], "gtin": p.get("gtin"),
                "name": p["name"], "brand": p["brand"], "category": p["category"],
                "package_quantity": p["package_quantity"], "package_unit": unit,
                "quantity_confidence": p["quantity_confidence"], "sale_model": p["sale_model"],
                "source_provenance": p["source_provenance"], "facts": f})
        if not evidence:
            pending.append({"identity": key, "reason": "Available suggestions fail exact whole label, food category, GTIN, package unit/form or quantity evidence",
                            "retrieved_products": entry["retrieved_products"]})
            continue
        name, form = key.split("|")
        accepted.append({"name": name, "form": form, "unit": unit,
            "requirements": ["pack:intake_all_" + hashlib.sha256(key.encode()).hexdigest()[:12]],
            "review_basis": f"Explicit full-label/category/GTIN or exact source identity/package review: {kind}. "
                + ("Source-estimated variable package mass; exact purchase is not certified and the existing consented estimated purchase contract remains mandatory. " if kind == "estimated_boneless" else "Exact source package amount. ")
                + "No density, shell/peel, cooking or drained conversion inferred. Unknown diet/nutrition/allergen/organic facts remain unknown.",
            "kind": kind, "evidence": evidence})
    definitions = pending_definitions(pending)
    TARGET.write_text(json.dumps({"schema_version": "smako-authoring-vocabulary-v1", "reviewed_at": "2026-10-26",
        "universe_sha256": report["universe_sha256"], "facts_sha256": report["facts_sha256"],
        "ingredients": accepted + definitions}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / ".local/recipes/all-ingredient-decisions.json").write_text(json.dumps({"pending": pending}, ensure_ascii=False, indent=2), encoding="utf-8")
    print({"new_identities": len(accepted), "references": sum(len(r["evidence"]) for r in accepted), "pending": len(pending)})


if __name__ == "__main__":
    build(ROOT / ".local/recipes/all-ingredient-research-catalog.json")
