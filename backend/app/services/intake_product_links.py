"""Reviewed exact public product identities; never price or personal approval."""
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

from app.models.product import QuantityConfidence
from app.services.ingredient_normalizer import _search_text

PATH = Path(__file__).parents[1] / "data/ingredients/intake-all-20261026.json"


@lru_cache(maxsize=1)
def entries():
    rows = json.loads(PATH.read_bytes())["ingredients"]
    rows.extend(json.loads(PATH.with_name("recipe-shapes-20261026.json").read_bytes())["ingredients"])
    rows.extend(json.loads(PATH.with_name("expansion-20261101.json").read_bytes())["ingredients"])
    rows.extend(json.loads(PATH.with_name("expansion-round2-20261101.json").read_bytes())["ingredients"])
    rows.extend(json.loads(PATH.with_name("expansion-round4-20261102.json").read_bytes())["ingredients"])
    return {row["requirements"][0].removeprefix("pack:"): row for row in rows}


# Authored recipes ask for fresh leaves ("raw_edible"); the reviewed registry
# so far only listed frozen chopped packs. A plain fresh bunch of the same herb
# is the same food. Owner decision 2026-11-07: accept it by identity, but only
# on its own exact published package mass (no density, yield or per-piece
# estimate) and only from a fresh-produce shelf, so dried jars stay out.
FRESH_HERBS = {"koriander": r"koriander", "gräslök": r"gräslök"}
FRESH_HERB_DESCRIPTORS = r"(?:eko|ekologisk|ekologiska|svensk|svenska|sverige|klass [12]|krav|färsk|färska|knippe|i knippe|i ask|ask|blad)"
# Cut-herb bunches weigh grams to tens of grams. A larger "package" on a fresh
# herb row is a source quantity we cannot trust as edible leaves.
FRESH_HERB_MAX_GRAMS = 150.0


def fresh_herb_alternative(row, product, fact=None):
    canonical = row["name"]
    if row["kind"] != "frozen_edible" or row["form"] != "raw_edible" or canonical not in FRESH_HERBS:
        return False
    label = " ".join(product.name.casefold().replace(",", " ").split())
    brand = " ".join((getattr(product, "brand", None) or "").casefold().split())
    if brand and brand != canonical and label.startswith(brand + " "):
        label = label[len(brand) + 1:]
    label = re.sub(r"\b\d+(?:[,.]\d+)?\s*(?:g|gr)\b", "", label)
    label = " ".join(label.split())
    descriptor = FRESH_HERB_DESCRIPTORS
    if not re.fullmatch(rf"(?:{descriptor} )*{FRESH_HERBS[canonical]}(?: {descriptor})*", label):
        return False
    category = (getattr(product, "category", None) or "").casefold()
    if not re.search(r"frukt|grönt|grönsak|kryddväxt", category) or re.search(r"fryst|skafferi|torkad", category):
        return False
    composition = " ".join(fact.ingredients).casefold().split("kan innehålla")[0] if fact else ""
    if re.search(r"\b(?:salt|socker|olja|smör|grädde|vitlök)\b", composition):
        return False
    return (getattr(product, "sale_model", None) == "fixed_package" and product.purchase_terms is None
            and product.package_unit == product.usable_unit == row["unit"] == "g"
            and product.usable_quantity == product.package_quantity
            and 0 < product.usable_quantity <= FRESH_HERB_MAX_GRAMS
            and getattr(product, "quantity_confidence", None) == QuantityConfidence.EXACT)


# Owner decision 2026-11-07: where an authored identity has no supplier
# declaration of edible/drained mass, Smako may plan with the exact published
# package mass instead. This only covers the identities listed here; for fresh
# avocado that mass includes peel and stone, so the recipe gets somewhat less
# flesh than written. Identity, shelf, composition and exact quantity remain.
PACKAGE_WEIGHT_IDENTITIES = {
    # Firm whole avocados for wedges/sticks; diced, frozen and ready-to-eat
    # (soft) fruit are other authored forms.
    ("avokado", "raw_edible"): (
        r"(?:\d+-pack )?(?:avokado|avocado)(?: (?:hass|eko|ekologisk|ekologiska|klass [12]|stor|\d+-pack))*",
        r"frukt|grönt", r"tärn|fryst|guacamole|kräm|mogen|olja", r"\b(?:salt|socker|olja|kryddor)\b|citron|syra"),
    # Cheese without brine: shredded mozzarella is sold and used by its net mass.
    ("mozzarella", "as_sold"): (
        r"(?:riven )?mozzarella(?: (?:riven|familjefavoriter|laktosfri|eko|ekologisk|\d+%))*",
        r"riven ost", r"pizza|sticks|paj|gnocchi|burrata|bufala|\blag\b|mini|kul|boll", r"\b(?:lag|vatten|kryddor|örter|vitlök)\b"),
    # Dry rice-paper sheets: the package mass is the dry sheet mass.
    ("rispapper", "dry"): (
        r"rispapper(?: (?:rund|runda|fyrkantig|\d+ ?cm|vietnamesisk|eko|ekologisk))*",
        r"rispapper", r"rulle|rullar|färdig|wrap", r"\b(?:socker|olja)\b|kryddor"),
    ("rispapper", "as_sold"): (
        r"rispapper(?: (?:rund|runda|fyrkantig|\d+ ?cm|vietnamesisk|eko|ekologisk))*",
        r"rispapper", r"rulle|rullar|färdig|wrap", r"\b(?:socker|olja)\b|kryddor"),
    # Canned bamboo shoots: shops publish only the net mass including brine,
    # so the recipe gets less drained bamboo than written.
    ("bambuskott", "preserved_drained"): (
        r"bambuskott(?: (?:skivade|strimlade|i bitar|hela|eko|ekologiska))*",
        r"konserv|bambuskott", r"sås|wok|mix", r"\b(?:socker|olja|chili)\b|kryddor"),
    # Plain hot-smoked salmon portions; the mass may include skin.
    ("varmrökt lax", "as_sold"): (
        r"varmrökt lax(?: (?:naturell|portionsbit|portionsbitar|dubbelbit|enkelfilé|i bit|bit))*",
        r"fisk|rökt|lax", r"peppar|citron|glaze|chili|dill|örter|mexican|kryddad|honung",
        r"\b(?:socker|peppar|kryddor|olja|honung)\b"),
    # Blue-mould cheese itself; processed spreads ("Ädelost Mjukost", smältost)
    # and flavoured cheeses are other foods.
    ("ädelost", "as_sold"): (
        r"(?:ädelost(?: danablu| special)?|danablu|gräddädel)(?: (?:eko|ekologisk|classic|halvmåne|extra creamy|grädd|\d+(?:[,.]\d+)? ?%))*",
        r"ost|blåmögel", r"mjukost|päron|smält|bredbar",
        r"smältsalt|vatten|hårdost|päron"),
    # Owner request 2026-11-21 ("lös alla blockerande ingredienser"): inputs
    # that had no reviewed product left in Lund or Malmö. Each pattern was
    # checked against every keyword-matching product in both cities; drained
    # forms are planned by package mass under the 2026-11-13 decision.
    # Fresh mozzarella in brine; the package mass includes the brine.
    ("mozzarella", "preserved_drained"): (
        r"(?:mini ?)?mozzarella(?: (?:di bufala|bufala|boll|bollar|kula|kulor|minibollar|mini|italiensk|classic|light|laktosfri|eko|ekologisk|fresh|fior di latte|\d+(?:[,.]\d+)? ?%|\d+-pack))*",
        r"ost|mozzarella", r"riven|pizza|sticks|paj|gnocchi|burrata|skivad|skivor|panerad|tomat|pesto|sallad",
        r"\b(?:kryddor|örter|vitlök|olja|basilika|tomat|chili)\b"),
    # Halloumi as sold (block).
    ("halloumi", "as_sold"): (
        r"halloumi(?: (?:ost|grillost|original|light|lätt|eko|ekologisk|block|\d+(?:[,.]\d+)? ?%))*",
        r"ost|halloumi", r"fries|strips|chili|krydd|panerad|wrap|burgare|smaksatt|tärnad",
        r"\b(?:chili|kryddor|vitlök)\b"),
    # Coarse maize grits / polenta; dry mass.
    ("majsgryn", "dry"): (
        r"(?:glutenfri )?(?:polenta(?: majsgryn| eko| ekologisk| grovmalen)*|majsgryn(?: eko| ekologisk| polenta)*|majsmjöl polenta grovmalen)",
        r"gryn|skafferi|mjöl|polenta|majs", r"snabb|färdig|instant|kaka|kakor|chips|flingor", r"\b(?:salt|socker|olja|vatten)\b"),
    ("polenta", "dry"): (
        r"(?:glutenfri )?(?:polenta(?: majsgryn| eko| ekologisk| grovmalen| finmalen)*|majsgryn(?: eko| ekologisk| polenta)*|majsmjöl polenta (?:grovmalen|finmalen))",
        r"gryn|skafferi|mjöl|polenta|majs", r"snabb|färdig|instant|kaka|kakor|chips|flingor", r"\b(?:salt|socker|olja|vatten)\b"),
    # Cooked peeled prawns, frozen or in brine; the mass may include glaze or brine.
    ("räkor", "cooked_drained"): (
        r"(?:sallads)?räkor(?: (?:handskalade|skalade|i lake|kokta|kokta & skalade|vannamei|vannamei kokta & skalade|msc|s|m|l|xl|\d+/\d+))*",
        r"räk|skaldjur|fisk", r"panerad|smaksatt|ramslök|med skal|rå|scampi|sallad med|röra|chili|vitlök|tempura|nudlar|paj",
        r"\b(?:socker|olja|kryddor|ramslök|vitlök|chili)\b|panering|vetemjöl"),
    # Artichoke hearts in brine (not oil-marinated).
    ("kronärtskocka", "preserved_drained"): (
        r"kronärtskocks-?hjärtan(?: (?:i lag|hela|halvor|kvartar|eko|ekologiska))*",
        r"konserv|grönsak|skafferi|kronärtskock", r"olja|marinerad|grillad|kräm|tapenade", r"\bolja\b|örter|vitlök"),
    # Japonica sushi rice, dry.
    ("sushiris", "dry"): (
        r"(?:sushi ?ris|sushi rice)(?: (?:eko|ekologiskt|japanskt|\d+-pack))*",
        r"ris|skafferi|asien|sushi", r"vinäger|kit|färdig|kokt|krisp", r"\b(?:salt|socker|vinäger|olja)\b"),
    # Sauerkraut; the mass includes its brine.
    ("surkål", "preserved_drained"): (
        r"(?:wein)?surkål(?: (?:klassisk|original|mild|eko|ekologisk|på burk|i burk))*",
        r"konserv|grönsak|surkål|inlagt|skafferi", r"rödkål|kimchi|vin|kryddad|bacon", r"\b(?:socker|olja|bacon|vin)\b"),
    # Whole sardines in oil or water; the mass includes the oil.
    ("sardiner", "preserved_drained"): (
        r"sardiner(?: (?:i )?(?:olja|olivolja|solrosolja|vatten|vegetabilisk olja|eko|msc|\d+-pack))*",
        r"fisk|konserv|sardin|skafferi", r"tomat|chili|citron|pastej|krydd|vitlök",
        r"tomat|chili|citron|vitlök|kryddor"),
    # Grape leaves in brine.
    ("vinblad", "preserved_drained"): (
        r"(?:handplockade )?vinblad(?: (?:i lag|i saltlag|handplockade|eko|ekologiska))*",
        r"konserv|grönsak|vinblad|skafferi|världens", r"fyllda|dolma|ris", r"\bris\b|\bolja\b"),
    # Sheet gelatine by mass.
    ("gelatinblad", "as_sold"): (
        r"gelatin ?blad(?: (?:\d+-pack|\d+ st))?",
        r"bak|gelatin|skafferi|övrigt", r"pulver|vegansk|agar", r"agar|pektin"),
    # Plain black tea leaves sold by mass.
    ("svart te", "dry"): (
        r"svart te(?: (?:yellow label|english breakfast|ceylon|assam|eko|ekologiskt|lösvikt|\d+-pack))*",
        r"\bte\b", r"earl|grey|smak|chai|vanilj|citron|lemon|peach|mango|caramel|bär|jordgubb|mix|lady",
        r"arom|bergamott|skal|frukt|karamell|socker"),
    # Canned water chestnuts; mass includes the water.
    ("vattenkastanjer", "preserved_drained"): (
        r"(?:water chestnut slices )?vattenkastanj(?:er)?(?: (?:skivade|hela|i bitar))*",
        r"konserv|grönsak|skafferi|asien|vattenkastanj", r"sås|wok|mix", r"\b(?:socker|olja)\b"),
    # Shelled cooked mussels in water or frozen meat; not smoked or oiled.
    ("musslor", "cooked_drained"): (
        r"(?:blå)?musslor(?: (?:i vatten|i lag|utan skal|kokta|chilenska|msc))*",
        r"skaldjur|fisk|konserv|havsdelikatess|musslor", r"rökt|olja|sås|grädde|creme|crème|vongole|kammussl|mandel",
        r"^(?!.*(?:utan skal|vatten)).*|rökt|olja"),
    # Fresh mung bean sprouts (in Sweden sold as böngroddar).
    ("böngroddar", "raw_edible"): (
        r"(?:mungböns|bön)groddar(?: (?:ekologisk|ekologiska|eko|färska))*",
        r"frukt|grönt|grodd|sallad", r"konserv|lag|brine|alfalfa|ärt|rödbet|vete|mix|sallad med", r"vatten|salt|syra"),
    ("böngroddar", "as_sold"): (
        r"(?:mungböns|bön)groddar(?: (?:ekologisk|ekologiska|eko|färska))*",
        r"frukt|grönt|grodd|sallad", r"konserv|lag|brine|alfalfa|ärt|rödbet|vete|mix|sallad med", r"vatten|salt|syra"),
    ("groddade mungbönor", "as_sold"): (
        r"(?:mungböns|bön)groddar(?: (?:ekologisk|ekologiska|eko|färska))*",
        r"frukt|grönt|grodd|sallad", r"konserv|lag|brine|alfalfa|ärt|rödbet|vete|mix|sallad med", r"vatten|salt|syra"),
    # Tomatillo salsa verde.
    ("salsa verde av tomatillo", "as_sold"): (
        r"(?:salsa verde|tomatillo salsa)(?: (?:mild|medium|het|hot))*",
        r"sås|salsa|skafferi|mexik|tillbehör", r"pesto|ört|persilja", r"persilja|kapris|ansjovis"),
    # Dry-cured ham, sliced.
    ("lufttorkad skinka", "as_sold"): (
        r"(?:luftt?torkad skinka )?(?:prosciutto(?: crudo| di parma)?|jam[oó]n serrano(?: gts)?|serranoskinka|lufttorkad skinka)(?: (?:skivad|skivor|eko|\d+ mån))*",
        r"lufttork|chark|delikatess|pålägg|luftorkat|kött", r"pizza|melon|mix|tryffel|pancetta|ost", r"\b(?:socker|kryddor|ost)\b|vatten"),
    # Canned cooked green lentils; the mass includes the water.
    ("gröna linser", "cooked_drained"): (
        r"(?:gröna linser|linser gröna)(?: (?:eko|ekologiska|ekologisk|kokta|i vatten))*",
        r"linser|bönor|konserv|skafferi", r"torkad|curry|indian|cannellini|soppa|gryta|sallad",
        r"^(?!.*vatten).*|socker|olja|tomat|kryddor"),
    # Raw peeled prawns (frozen).
    ("råa räkor", "raw_edible"): (
        r"(?:scampi vannameiräka|vannamei ?räkor råa|råa (?:vannamei ?)?räkor|scampi)(?: (?:skalade|frysta|msc|asc|\d+/\d+))*",
        r"räk|skaldjur|fisk", r"panerad|kokt|marinerad|vitlök|chili|smaksatt|tempura", r"^(?!.*rå).*|vitlök|chili|olja|kryddor"),
    # Silken tofu.
    ("silkestofu", "as_sold"): (
        r"(?:tofu silkesmjuk|silkestofu|silken tofu|silkesmjuk tofu)(?: (?:eko|ekologisk|naturell))*",
        r"tofu|vegetar|asien|skafferi", r"rökt|marinerad|friterad|chili|örter", r"sojasås|kryddor|chili|olja"),
    # Puff pastry made without dairy or egg.
    ("vegansk smördeg", "as_sold"): (
        r"(?:glutenfri )?smördeg(?: (?:vegansk|glutenfri|laktosfri|fryst|plattor|rektangulär|rulle|kyld))*",
        r"paj|bak|smördeg|fryst|färdigmat|deg|julbord", r"stänger|twist|krustad|vol-au|bakverk",
        r"smör|mjölk|grädde|ägg|vassle|laktos(?!fri)"),
    # Matjes herring; mass includes the brine.
    ("matjessill", "preserved_drained"): (
        r"(?:bohus|mästar)?matjes(?:s?ill|filé|fileér|filéer)?(?: (?:hel|hela|i bitar|bitar|klassisk|mästar))*",
        r"sill|fisk", r"sås|tomat|röra|senap|löksill", r"tomat|senap|gräddfil|majonnäs"),
    # Plain roasted nori sheets.
    ("nori", "as_sold"): (
        r"(?:sjögräs )?(?:sushi nori|yaki nori(?: sushi)?|nori)(?: (?:roasted seeweed|roasted seaweed|ark|\d+-pack|sushi))*",
        r"tillbehör|skafferi|asien|sushi|nori", r"snacks|chips|krydd|wasabi|teriyaki|chili", r"\b(?:salt|olja|socker)\b|kryddor"),
    # Clarified butter.
    ("ghee", "as_sold"): (
        r"(?:klarnat smör )?ghee(?: (?:eko|ekologisk|nötig|skirat smör|klarnat smör))*",
        r"matfett|smör|ghee|skafferi|matolja", r"vegansk|växtbaser", r"olja|kryddor|vegetabil"),
    # Cured pork cheek (not pancetta or bacon).
    ("guanciale", "as_sold"): (
        r"guanciale(?: (?:stagionato|dolce|tärnad|skivad|i bit|bit))*",
        r"chark|delikatess|bacon|stekfläsk|kött", r"pancetta|bacon|pasta|sås", r"\b(?:kryddor|peppar|chili|vitlök)\b"),
    # Salt-brined dill cucumbers; mass includes brine.
    ("saltgurka", "preserved_drained"): (
        r"saltgurk(?:a|or)(?: (?:hel|hela|skivad|skivade|eko|ekologisk))*",
        r"gurka|inlagd|konserv|pickles|skafferi", r"chips|majonnäs|smörgås|relish", r"\bsötningsmedel\b"),
}


# Dry goods, plain foods and cured mixtures are matched by the same label,
# shelf, composition and exact-package gates as definition-only rows.
PACKAGE_WEIGHT_KINDS = {"definition_only", "dairy", "dry", "plain", "mixture"}


def _package_label(product):
    return " ".join(re.sub(r"\b\d+(?:[,.]\d+)?\s*(?:kg|g)\b", "", product.name.casefold()).split())


def package_weight_alternative(row, product, fact=None):
    entry = PACKAGE_WEIGHT_IDENTITIES.get((row["name"], row["form"]))
    if entry is None or row["kind"] not in PACKAGE_WEIGHT_KINDS or row["unit"] != "g":
        return False
    pattern, shelf, excluded, composition_excluded = entry
    label = _package_label(product)
    category = (getattr(product, "category", None) or "").casefold()
    if re.search(excluded, label) or re.search(excluded, category) or not re.search(shelf, category + " " + label):
        return False
    if not re.fullmatch(pattern, label):
        return False
    composition = " ".join(fact.ingredients).casefold().split("kan innehålla")[0] if fact else ""
    if re.search(composition_excluded, composition):
        return False
    if fact is not None:
        from app.services.complete_recipes import identity_conflicts
        from app.services.official_product_facts import _mass_blocking

        if _mass_blocking(fact.conflicts) or identity_conflicts(fact):
            return False
    return (getattr(product, "sale_model", None) == "fixed_package" and product.purchase_terms is None
            and product.package_unit == product.usable_unit == "g"
            and product.usable_quantity == product.package_quantity and product.usable_quantity > 0
            and getattr(product, "quantity_confidence", None) == QuantityConfidence.EXACT)


def _chain(store_id):
    parts = (store_id or "").split(":")
    return parts[1] if len(parts) > 2 and parts[0] == "context" else None


# Willys, Hemköp and City Gross publish the same article codes ("101083881_ST")
# for the same product. Owner report 2026-11-20: reviews made at City Gross or
# Hemköp Malmö left Lund (no City Gross) without products. One article code
# therefore identifies the product in all three chains; name, brand and
# package are still compared, the chains' own category trees are not.
ARTICLE_FAMILIES = {"willys": "axfood", "hemkop": "axfood", "citygross": "axfood"}


def _article_family(store_id):
    chain = _chain(store_id)
    return ARTICLE_FAMILIES.get(chain, chain)


def _articles(product, fact):
    """Retailer article ids of this exact product: its own provenance (unless
    that id is a flyer advertisement, not an article) and facts bound to this
    product and snapshot. Owner decision 2026-11-07: an article id identifies
    the same product in every store of the chain."""
    provenance = getattr(product, "source_provenance", None)
    found = set()
    article = getattr(provenance, "retailer_product_id", None) if provenance else None
    namespace = getattr(provenance, "retailer_id_namespace", None) or ""
    if article and not namespace.endswith("flyer-document-ad"):
        found.add(article)
    if (fact is not None and provenance is not None
            and getattr(fact, "source_product_id", None) == product.product_id
            and getattr(fact, "source_snapshot_id", None) == provenance.source_snapshot_id
            and getattr(fact, "retailer_product_id", None)):
        found.add(fact.retailer_product_id)
    return found


def same_chain_article(evidence, product, fact):
    return bool(evidence.get("retailer_product_id") and _chain(product.store_id)
                and _article_family(product.store_id) == _article_family(evidence["store_id"])
                and evidence["retailer_product_id"] in _articles(product, fact))


def compatible(key, product, fact=None):
    row = entries().get(key)
    if row is None:
        return False
    if fresh_herb_alternative(row, product, fact) or package_weight_alternative(row, product, fact):
        return True
    if row["kind"] == "definition_only":
        return reviewed_definition(row, product, fact) or declared_definition(row, product, fact)
    if fact is not None and row["kind"] in {"plain", "dry"}:
        composition = " ".join(fact.ingredients).casefold().split("kan innehålla")[0]
        excluded = r"\b(?:salt|socker|olja|smör|sirap|sugar|oil)\b"
        if re.search(excluded, composition) or (row["kind"] == "dry" and "vatten" in composition):
            return False
    # GTIN alone cannot hide a changed label, unit or package. Snapshot, price,
    # source qualification, edible forms and personal facts remain live gates.
    def identity(evidence):
        if evidence.get("gtin"):
            return str(getattr(product, "gtin", "")) == evidence["gtin"]
        provenance = getattr(product, "source_provenance", None)
        if same_chain_article(evidence, product, fact):
            # The retailer article id is the global identity that lets a
            # reviewed link survive a new collection and apply in every store
            # of the chain. It must come from this product's own provenance or
            # from facts bound to this exact product and snapshot; never from
            # its name. Name, brand and package are still compared below.
            return True
        return (product.product_id == evidence["product_id"] and product.store_id == evidence["store_id"]
                and provenance is not None and provenance.source_snapshot_id
                == evidence["source_provenance"]["source_snapshot_id"])

    return any(identity(evidence)
               and _search_text(product.name) == _search_text(evidence["name"])
               and _search_text(getattr(product, "brand", None) or "") == _search_text(evidence.get("brand") or "")
               and product.package_unit == evidence["package_unit"]
               and product.package_quantity == evidence["package_quantity"]
               and product.usable_unit == row["unit"]
               and product.usable_quantity == product.package_quantity
               and getattr(product, "quantity_confidence", None) == evidence.get("quantity_confidence", "exact")
               for evidence in row["evidence"])


# Composition of a link reviewed while the store published no ingredient list.
UNDECLARED_COMPOSITION = "b0e7b46e22f689bdb85a2ce14897b8ee7a968b529bac95ac593aa149c2979b9e"


def first_declaration(evidence, fact):
    """Owner report 2026-11-20: since declarations are collected with the
    products (2026-11-16), links reviewed without a declaration stopped
    matching, so olive oil, fish sauce and 38 more inputs had no product in
    Lund or Malmö. The review approved identity, form and quantity only. A
    declaration that appears later on the same article, name, brand, category
    and package is not changed content; allergy and exclusion gates still read
    it. A link reviewed against a declaration still needs that declaration."""
    if evidence.get("composition_sha256") != UNDECLARED_COMPOSITION or not fact.ingredients:
        return False
    # A link whose quantity review read a declaration knows the food's content.
    quantity = evidence.get("quantity") or {}
    return not (quantity.get("declared_ingredients") or quantity.get("label_source"))


REREVIEW_PATH = Path(__file__).parents[1] / "data/ingredients/composition-rereviews-20261120.json"


@lru_cache(maxsize=1)
def composition_rereviews():
    """Reviewed pin -> current declarations re-reviewed as the same food.

    Each accepted declaration is stored with its full text and checked here
    against its hash, so a changed text needs a new review."""
    if not REREVIEW_PATH.exists():
        return {}
    result = {}
    for item in json.loads(REREVIEW_PATH.read_text(encoding="utf-8"))["rereviews"]:
        for accepted in item["accepted"]:
            value = {"ingredients": accepted["ingredients"], "ingredients_complete": accepted["ingredients_complete"],
                     "ingredient_evidence_kind": accepted["ingredient_evidence_kind"]}
            digest = hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            if digest != accepted["composition_sha256"] or not accepted.get("review"):
                raise ValueError(f"composition re-review {accepted['composition_sha256']} does not match its text")
            result.setdefault(item["pin"], set()).add(digest)
    return {pin: frozenset(values) for pin, values in result.items()}


def composition_signature(fact):
    """Reviewed composition, independent of a catalogue's price generation.

    The caller separately verifies the current fact's product/snapshot binding.
    A new price document or UUID must not invalidate identical food content.
    """
    value = {name: getattr(fact, name, None) for name in (
        "ingredients", "ingredients_complete", "ingredient_evidence_kind")}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def same_label(evidence, product, global_identity=False):
    """The reviewed label. A product identified by GTIN or article code keeps
    its identity when a chain re-cases the brand ("GALBANI" -> "Galbani") or
    moves it in its own category tree, and Willys, Hemköp and City Gross each
    write their own (owner report 2026-11-20). Name and brand are compared
    without case or marks, the package exactly. A renamed product still needs
    review; a source-scoped link (no GTIN or article) stays exact."""
    if not global_identity:
        return not any(getattr(product, field, None) != evidence.get(field)
                       for field in ("name", "brand", "category", "package_quantity", "package_unit", "sale_model"))
    same_brand = _search_text(getattr(product, "brand", None) or "") == _search_text(evidence.get("brand") or "")
    same_name = _search_text(product.name) == _search_text(evidence["name"])
    # A fresh-produce yield belongs to the produce shelf; there the category
    # is part of the identity (a product moved to dairy is another food).
    if evidence.get("identity_basis") == "whole_fresh_produce" and getattr(product, "category", None) != evidence.get("category"):
        if _chain(product.store_id) == _chain(evidence["store_id"]) or not re.search(r"frukt|grönt|grönsak", (getattr(product, "category", None) or "").casefold()):
            return False
    return (same_brand and same_name
            and all(getattr(product, field, None) == evidence.get(field)
                    for field in ("package_quantity", "package_unit", "sale_model")))


def _review_identity(evidence, product, fact):
    provenance = getattr(product, "source_provenance", None)
    original = evidence.get('source_provenance', {})
    # Stable, exact food identity; the live price, qualification and request
    # scope remain downstream gates. Unidentified rows retain the snapshot and
    # store gate; a GTIN or retailer article identifies the product in every
    # store of the same chain (owner decision 2026-11-07).
    if evidence.get('gtin'):
        identified = evidence['gtin'] == getattr(product, 'gtin', None)
        global_identity = True
    elif evidence.get('retailer_product_id'):
        identified = same_chain_article(evidence, product, fact)
        global_identity = True
    else:
        identified = (evidence['product_id'] == product.product_id and provenance
                      and evidence['source_snapshot_id'] == provenance.source_snapshot_id)
        global_identity = False
    same_store = evidence["store_id"] == product.store_id
    same_chain = _chain(evidence["store_id"]) is not None and _chain(evidence["store_id"]) == _chain(product.store_id)
    other_chain = (global_identity and not same_chain and _chain(product.store_id) is not None
                   and (evidence.get("gtin") or _article_family(evidence["store_id"]) == _article_family(product.store_id)))
    store_fields = ('source_provider', 'source_channel', 'source_role')
    if not other_chain:
        store_fields += ('chain', 'price_context', 'retailer_id_namespace')
    if not global_identity or same_store:
        store_fields += ('provider_store_id',)
    if (not provenance or not evidence.get("review") or not evidence.get("source_sha256")
            or not (same_store or (global_identity and (same_chain or other_chain)))
            or not identified
            or any(getattr(provenance, field, None) != original.get(field) for field in store_fields)
            # Willys and Hemköp rows carry no GTIN; a City Gross review may.
            or ((evidence.get("gtin") or None) != (getattr(product, "gtin", None) or None)
                and not (other_chain and evidence.get("gtin") and not getattr(product, "gtin", None)))
            or not same_label(evidence, product, global_identity)):
        return False
    if fact is not None:
        from app.services.complete_recipes import identity_conflicts
        from app.services.official_product_facts import _mass_blocking

        if (_mass_blocking(fact.conflicts) or identity_conflicts(fact)
                or fact.source_product_id != product.product_id
                or fact.source_snapshot_id != provenance.source_snapshot_id):
            return False
    if evidence.get("composition_sha256"):
        return bool(fact and fact.source_product_id == product.product_id
                    and fact.source_snapshot_id == provenance.source_snapshot_id
                    and (composition_signature(fact) == evidence["composition_sha256"]
                         or first_declaration(evidence, fact)
                         or composition_signature(fact) in composition_rereviews().get(evidence["composition_sha256"], ())))
    return (evidence.get("identity_basis") == "whole_fresh_produce"
            and not (fact and fact.ingredients))


def reviewed_definition(row, product, fact):
    """Independent identity/form and quantity review; no personal fact approval."""
    for proof in row.get("reviewed_links", ()):
        if not _review_identity(proof, product, fact):
            continue
        quantity = proof["quantity"]
        if (quantity["unit"] == row["unit"] == product.usable_unit
                and quantity["usable_quantity"] == product.usable_quantity
                and quantity["confidence"] == product.quantity_confidence
                and quantity["basis"] == row["form"]):
            return True
    return False


def reviewed_drained_quantity(canonical, form, requirements, product, fact):
    """A source-bound declared drained mass can also live in the review registry."""
    for requirement in requirements:
        row = entries().get(requirement.removeprefix('pack:'), {})
        if row.get('name') != canonical or row.get('form') != form:
            continue
        for proof in row.get('reviewed_links', ()):
            quantity = proof['quantity']
            if quantity.get('method') == 'reviewed_source_already_drained_mass_v1':
                source, label = quantity.get('source', {}), quantity.get('label_source', {})
                if (quantity.get('form_evidence_location') == 'review_registry'
                        and quantity.get('source_quantity_basis') == 'declared_drained'
                        and _review_identity(proof, product, fact)
                        and product.sale_model == 'fixed_package' and product.purchase_terms is None
                        and product.package_unit == product.usable_unit == quantity['unit'] == 'g'
                        and 0 < quantity.get('declared_drained_quantity', 0)
                        == quantity['usable_quantity'] == product.usable_quantity == product.package_quantity
                        <= quantity.get('declared_net_quantity', 0)
                        and quantity['basis'] == form and form in {'preserved_drained', 'cooked_drained'}
                        and product.quantity_confidence == quantity['confidence'] == 'exact'
                        and all(s.get('sha256') and s.get('url')
                                and s.get('evidence_kind') == 'reviewed_manufacturer_drained_mass'
                                and s.get('declared_net_g') == quantity['declared_net_quantity']
                                and s.get('declared_drained_g') == quantity['declared_drained_quantity']
                                for s in (source, label))):
                    return True
                continue
            if (quantity.get('method') == 'reviewed_declared_drained_mass_v1'
                    and quantity.get('form_evidence_location') == 'review_registry'
                    and _review_identity(proof, product, fact)
                    and product.sale_model == 'fixed_package' and product.purchase_terms is None
                    and product.package_unit == product.usable_unit == quantity['unit'] == 'g'
                    and quantity.get('declared_net_quantity') == product.package_quantity
                    and 0 < quantity['usable_quantity'] == product.usable_quantity <= product.package_quantity
                    and quantity['basis'] == form and form in {'preserved_drained', 'cooked_drained'}
                    and product.quantity_confidence == quantity['confidence'] == 'exact'
                    and quantity.get('source', {}).get('sha256')
                    and quantity.get('label_source', {}).get('sha256')):
                return True
    return False


@lru_cache(maxsize=1)
def _quantity_reviews():
    result = {}
    for row in entries().values():
        for proof in row.get("reviewed_links", ()):
            if proof["quantity"].get("method") in {
                "usda_sr28_refuse_v1", "matvaretabellen_edible_fraction_v1",
                "reviewed_declared_drained_mass_v1",
                "reviewed_declared_piece_count_v1",
            }:
                # Global identities are looked up per chain; _review_identity
                # still checks the exact product, label and package.
                key = (('gtin', _chain(proof['store_id']), proof['gtin']) if proof.get('gtin')
                       else ('article', _chain(proof['store_id']), proof['retailer_product_id'])
                       if proof.get('retailer_product_id') else ('product', proof['store_id'], proof['product_id']))
                result.setdefault(key, []).append(proof)
    return result


def project_reviewed_quantity(product, fact, *, allow_estimates=False, required_unit=None):
    """Project reviewed usable quantity; retain gross package and source time.

    Declared drained contents are exact; population edible yields need consent.
    Every review retains the exact source product, context and gross package.
    """
    if required_unit not in {"g", "st"}:
        return product
    chain = _chain(product.store_id)
    keys = [('gtin', chain, getattr(product, 'gtin', None)),
            *(('article', chain, article) for article in sorted(_articles(product, fact))),
            ('product', product.store_id, product.product_id)]
    proofs = [proof for key in keys for proof in _quantity_reviews().get(key, ())]
    for proof in proofs:
        q = proof["quantity"]
        if q.get('method') == 'reviewed_declared_piece_count_v1':
            quantity = q.get('usable_quantity')
            source = q.get('source', {})
            if (required_unit == 'st' and _review_identity(proof, product, fact)
                    and fact is not None and fact.ingredients_complete
                    and product.sale_model == 'fixed_package' and product.package_unit == 'g'
                    and product.quantity_confidence == 'exact' and product.purchase_terms is None
                    and q.get('confidence') == 'exact' and q.get('basis') == 'as_sold'
                    and q.get('unit') == 'st' and q.get('declared_net_quantity') == product.package_quantity
                    and isinstance(quantity, int) and not isinstance(quantity, bool) and 0 < quantity < 100000
                    and source.get('evidence_kind') == 'reviewed_manufacturer_count_declaration'
                    and source.get('sha256') and source.get('url')
                    and source.get('consumer_gtin') == proof.get('gtin') == product.gtin
                    and product.gtin is not None and source.get('declared_piece_count') == quantity
                    and source.get('declared_net_g') == product.package_quantity):
                return product.model_copy(update={'usable_quantity': quantity, 'usable_unit': 'st',
                                                   'quantity_confidence': QuantityConfidence.EXACT})
            continue
        if required_unit != 'g':
            continue
        if q.get('method') == 'reviewed_declared_drained_mass_v1':
            quantity = q.get('usable_quantity')
            if (_review_identity(proof, product, fact)
                    and product.sale_model == 'fixed_package' and product.package_unit == 'g'
                    and product.purchase_terms is None
                    and q.get('confidence') == 'exact'
                    and q.get('basis') in {'preserved_drained', 'cooked_drained'}
                    and q.get('unit') == 'g' and q.get('declared_net_quantity') == product.package_quantity
                    and isinstance(quantity, (int, float)) and not isinstance(quantity, bool)
                    and 0 < quantity <= product.package_quantity
                    and q.get('source', {}).get('sha256')
                    and q.get('label_source', {}).get('sha256')):
                return product.model_copy(update={'usable_quantity': quantity, 'usable_unit': 'g',
                                                   'quantity_confidence': QuantityConfidence.EXACT})
            continue
        if (not _review_identity(proof, product, fact)
                or not allow_estimates
                or product.sale_model not in {"fixed_package", "variable_weight_package"} or product.package_unit != "g"
                or product.purchase_terms is not None
                or q.get("confidence") != "estimated" or q.get("basis") != "raw_edible"
                or q.get("source", {}).get("sha256") is None
                or not 0 < q.get("edible_fraction", 0) < 1
                or q["usable_quantity"] != round(product.package_quantity * q["edible_fraction"], 8)):
            continue
        return product.model_copy(update={"usable_quantity": q["usable_quantity"], "usable_unit": "g",
                                          "quantity_confidence": "estimated"})
    return product


def declared_definition(row, product, fact):
    """A reviewed definition supplies no product evidence by itself.

    Reuse the ordinary, exact supplier declaration gate. The declaration must
    additionally state this input's usable mass/volume and basis, including
    edible-only or drained contents where required. A label, invented form tag,
    generic nutrition reference or net whole-fruit weight cannot supply that.
    """
    from types import SimpleNamespace

    from app.services.complete_recipes import _supplier_classification

    if (fact is None or getattr(fact, "conflicts", ())
            or product.usable_unit != row["unit"]
            or getattr(product, "quantity_confidence", None) != "exact"):
        return False
    basis = {"raw_edible": "edible_as_sold", "dry": "dry",
             "cooked_drained": "cooked_drained", "preserved_drained": "preserved_drained",
             "as_sold": "as_sold"}[row["form"]]
    for proof in fact.field_sources.get("product_classification", ()):
        if (proof.get("kind") != "manufacturer_culinary_declaration"
                or proof.get("declared_usable_quantity") != product.usable_quantity
                or proof.get("declared_usable_unit") != row["unit"]
                or proof.get("declared_quantity_basis") != basis):
            continue
        view = SimpleNamespace(product_classification=fact.product_classification,
            field_sources={"product_classification": (proof,)})
        if _supplier_classification(product, view, row["required_classification"]):
            return True
    return False


def gross_purchase_input(recipe, name):
    """Gross bone/pod/shell/cob mass has no supported edible nutrition yield."""
    for ingredient in recipe.ingredients:
        if ingredient.canonical_name == name:
            for requirement in ingredient.product_requirements or ():
                row = entries().get(requirement.removeprefix("pack:"), {})
                if row.get("gross_inedible_mass"):
                    return True
    return False


def recipe_product(recipe, name, product, fact=None):
    from app.services.ingredient_normalizer import canonicalize_ingredient_name

    canonical = canonicalize_ingredient_name(name)
    for ingredient in recipe.ingredients:
        if ingredient.canonical_name != canonical:
            continue
        if ingredient_product(canonical, ingredient.form, ingredient.product_requirements or (), product, fact):
            return True
    return False


def package_weight_product(canonical, form, requirements, product, fact=None):
    """An owner-approved package-mass identity counts as the reviewed form."""
    for requirement in requirements:
        if requirement.startswith("pack:intake_all_"):
            row = entries().get(requirement.removeprefix("pack:"))
            if row and row["name"] == canonical and row["form"] == form and package_weight_alternative(row, product, fact):
                return True
    return False


def ingredient_product(canonical, form, requirements, product, fact=None, *, reviewed_only=False):
    for requirement in requirements:
        if requirement.startswith("pack:intake_all_"):
            key = requirement.removeprefix("pack:")
            row = entries().get(key)
            if row and row["name"] == canonical and row["form"] == form:
                if reviewed_only:
                    if row["kind"] == "definition_only" and (reviewed_definition(row, product, fact)
                                                             or package_weight_alternative(row, product, fact)):
                        return True
                elif compatible(key, product, fact):
                    return True
    return False


@lru_cache(maxsize=1)
def reference_version():
    rereviews = {pin: sorted(values) for pin, values in composition_rereviews().items()}
    return hashlib.sha256(json.dumps([entries(), rereviews] if rereviews else entries(),
                                     ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def search_positions(prepared, facts=None):
    """Index exact public identifiers once per existing prepared universe.

    Ingredient query spelling does not have to match a retailer's spelling.
    These positions are retrieval only; all request gates run after retrieval.
    Retailer article ids come from each product's provenance or from facts
    bound to that exact product and snapshot, so reviewed links keep finding
    the same article after a new collection.
    """
    def compute():
        gtins, scoped, articles = {}, {}, {}
        for row in entries().values():
            for evidence in row.get("reviewed_links", ()):
                if evidence.get("retailer_product_id"):
                    articles.setdefault((_chain(evidence["store_id"]), evidence["retailer_product_id"]), set()).add(row["name"])
                key = (evidence["store_id"], evidence["product_id"], evidence["source_snapshot_id"])
                scoped.setdefault(key, set()).add(row["name"])
                if evidence.get('gtin'):
                    gtins.setdefault(evidence['gtin'], set()).add(row['name'])
            if row["kind"] == "definition_only":
                continue
            for evidence in row["evidence"]:
                if evidence.get("gtin"):
                    gtins.setdefault(evidence["gtin"], set()).add(row["name"])
                else:
                    if evidence.get("retailer_product_id"):
                        articles.setdefault((_chain(evidence["store_id"]), evidence["retailer_product_id"]), set()).add(row["name"])
                    key = (evidence["store_id"], evidence["product_id"], evidence["source_provenance"]["source_snapshot_id"])
                    scoped.setdefault(key, set()).add(row["name"])
        positions = {}
        # Package-mass identities are found by their reviewed label pattern:
        # a retailer may index "Glutenfri Polenta Eko" under polenta, not
        # majsgryn. Retrieval only; package_weight_alternative still decides.
        labelled = [(name, re.compile(entry[0])) for (name, _form), entry in PACKAGE_WEIGHT_IDENTITIES.items()]
        for n, product in enumerate(prepared.universe.products):
            provenance = product.source_provenance
            key = (product.store_id, product.product_id, provenance.source_snapshot_id if provenance else None)
            names = gtins.get(getattr(product, "gtin", None), set()) | scoped.get(key, set())
            label = _package_label(product)
            names = names | {name for name, pattern in labelled if pattern.fullmatch(label)}
            if articles:
                fact = facts.get((product.store_id, product.product_id)) if facts is not None else None
                for article in _articles(product, fact):
                    names = names | articles.get((_chain(product.store_id), article), set())
            for name in names:
                positions.setdefault(name, set()).add(n)
        return MappingProxyType({name: frozenset(values) for name, values in positions.items()})

    version = "" if facts is None else ":" + str(getattr(facts, "version", None) or id(facts))
    return prepared.product_search_cache.get_or_compute("reviewed-intake-exact:" + reference_version() + version, compute)
