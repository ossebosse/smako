"""Request translation and hard authored-recipe boundaries, using PersonalPlanner.

There is no second price engine. Public dinners become private meal slots before
admission and persistence so the exact same policies survive later revisions.
"""
from __future__ import annotations

import re

from app.models.personal import MealSettings, PersonalPlanning, PortionLimits
from app.services.personal_policy import PolicyConflict


def enabled(request):
    return bool(request.recipe_preferences and request.recipe_preferences.mode == "complete")


def prepare_request(request, settings, *, pantry_revision=0):
    if not enabled(request):
        return request
    if not settings.complete_recipes_enabled:
        raise PolicyConflict("Genomarbetade middagar är inte aktiverade i denna miljö. Välj befintligt receptläge.", code="FEATURE_DISABLED")
    prefs = request.recipe_preferences
    if request.personal is None:
        spec = PersonalPlanning(
            meals=[MealSettings(count=request.recipes, servings=request.servings,
                                diet=request.diet_preference.value if request.diet_preference.value in {"vegetarian", "vegan"} else "mixed")],
            pantry_revision=pantry_revision,
            allow_nutrition_estimates=request.allow_nutrition_estimates,
            use_pantry=request.use_pantry,
        )
    else:
        spec = request.personal.model_copy(deep=True)
    for meal in spec.meals:
        if meal.meal_type != "dinner" or not meal.count:
            continue
        if request.diet_preference.value in {"vegetarian", "vegan"} and meal.diet != request.diet_preference.value:
            raise PolicyConflict("Måltidens kostval strider mot planens kostval. Använd samma kostinriktning i båda valen.", code="RECIPE_CHOICES_CONFLICT")
        if not prefs.allow_fish and meal.distribution.get("fish", 0):
            raise PolicyConflict("Fisk är avstängd men ingår i vald fördelning. Ta bort fiskmåltiderna eller tillåt fisk.", code="RECIPE_CHOICES_CONFLICT")
        if prefs.min_protein_g is not None:
            limits = meal.limits.model_dump()
            limits["min_protein_g"] = max(prefs.min_protein_g, meal.limits.min_protein_g or 0)
            if limits["max_protein_g"] is not None and limits["max_protein_g"] < limits["min_protein_g"]:
                raise PolicyConflict("Proteinmålet överstiger måltidens maxgräns. Ändra en av proteingränserna.", code="RECIPE_CHOICES_CONFLICT")
            meal.limits = PortionLimits.model_validate(limits)
    from app.models.diversity import DiversityPolicyOverrides
    overrides = request.recipe_diversity_overrides
    if overrides is None:
        # Persist explicit choices once. model_fields_set is not preserved by
        # ordinary JSON reload; otherwise omitted legacy defaults reappear as
        # user overrides when a complete plan is explicitly recalculated.
        values = {key: getattr(request, key) for key in DiversityPolicyOverrides.model_fields
                  if key in request.model_fields_set}
        if "max_pairwise_recipe_similarity" in request.model_fields_set and "max_pairwise_culinary_similarity" not in values:
            values["max_pairwise_culinary_similarity"] = request.max_pairwise_recipe_similarity
        overrides = DiversityPolicyOverrides.model_validate(values).model_dump(exclude_unset=True)
    return request.model_copy(update={"personal": spec, "strategy": "optimized", "recipe_diversity_overrides": overrides})


def diversity_policy(request, policy):
    """Keep price goals and explicit limits; judge authored dinners together.

    Repeated rice or a saucepan alone does not make two complete meals copies.
    Family/main/dish limits and multi-factor near-duplicate rejection remain;
    Varied still needs real changes versus Balanced within its price ceiling.
    """
    if not enabled(request):
        return policy
    overrides = request.recipe_diversity_overrides
    return policy.model_copy(update={
        "policy_version": "authored-meal-multifactor-v1", "min_cooking_methods": 0,
        "max_same_cooking_method_meals": None, "max_same_carbohydrate_meals": None,
        **(overrides or {}),
    })


def identity(recipe):
    d = recipe.design
    return f"{d.base_id}:{d.version}:{d.variant_id}" if d else None


def matches_preferences(recipe, preferences):
    from app.services.recipe_library import ingredient_count, validate_recipe_design

    validate_recipe_design(recipe)
    d = recipe.design
    if not d or preferences.cuisines and not set(preferences.cuisines) & set(d.cuisines):
        return False
    if not preferences.min_ingredients <= ingredient_count(recipe) <= preferences.max_ingredients:
        return False
    if preferences.max_minutes is not None and d.estimated_minutes > preferences.max_minutes:
        return False
    from app.services.personal_policy import protein_category
    if not preferences.allow_fish and protein_category(recipe) == "fish":
        return False
    return not (preferences.adaptation == "products" and d.variant_id != "base")


def validate_content_capacity(preferences, meal, profile, candidates):
    """Prove only an authored-content shortage, before source qualification.

    Variants cannot supply additional distinct dinners. The library filter and
    existing hard dietary/exclusion rules are exhaustive for this content check;
    sufficient content never promises source coverage or a feasible weekly buy.
    """
    from app.services.diet_policy import recipe_respects_diet
    from app.services.recipe_library import candidates as library_candidates

    def eligible(recipes):
        return [recipe for recipe in recipes if recipe_respects_diet(
            recipe, preference=meal.diet,
            avoid_ingredients=profile.exclusions + profile.allergies)]

    available = eligible(candidates)
    count = len({recipe.design.base_id for recipe in available})
    if count >= meal.count:
        return
    suggestions = []
    if preferences.max_minutes is not None:
        without_time = eligible(library_candidates(
            preferences.model_copy(update={"max_minutes": None}), meal.servings))
        earliest = {}
        for recipe in without_time:
            key = recipe.design.base_id
            earliest[key] = min(earliest.get(key, float("inf")), recipe.design.estimated_minutes)
        if len(earliest) >= meal.count:
            minimum = sorted(earliest.values())[meal.count - 1]
            suggestions.append(f"Höj högsta tillagningstid till minst {minimum:g} minuter")
    if count:
        suggestions.append(f"välj högst {count} middagar")
    if not suggestions:
        suggestions.append("Utöka matkök eller ingrediensintervall, eller ändra kostval och uteslutningar uttryckligen")
    raise PolicyConflict(
        f"Biblioteket innehåller {count} distinkta grundrätter för {meal.servings} personer "
        f"med dina val av matkök, ingrediensantal, tid, anpassningar och kost; du har valt {meal.count} middagar. "
        + ", eller ".join(suggestions) + ". "
        "Detta är en innehållskontroll före produkt-, närings- och inköpskvalificering; fler kandidater garanterar inte en köpbar meny. Dina krav har inte ändrats.",
        code="RECIPE_CHOICES_CONFLICT", stage="policy_taste")


def completed_search_outcome(diagnostics):
    """A valid checkout and a reached sub-search limit can both be true.

    These counters describe the recorded planner search. Omitted diagnostic
    details cannot establish that no nutrition search reached its limit.
    Equivalence pruning does not spend the beam budget on different menus.
    """
    nutrition = diagnostics.get("nutrition_searches", [])
    omitted = diagnostics.get("omitted_nutrition_searches", 0)
    exhausted = sum(bool(row.get("budget_exhausted")) for row in nutrition)
    status = "REACHED" if exhausted else "UNKNOWN" if omitted else "NOT_REACHED"
    pruned = sum(max(0, row.get("beam_pruned", 0) - row.get("equivalent_pruned", 0))
                 for row in diagnostics.get("search", []))
    if exhausted:
        message = (f"En giltig meny hittades. Sökbudgeten nåddes i {exhausted} registrerade "
                   "näringsdelberäkningar; andra godkända produktkombinationer kan finnas.")
    elif omitted:
        message = ("En giltig meny hittades. Sökningen är begränsad och delar av sökloggen "
                   "saknas; det går inte att fastställa om alla näringsdelberäkningar höll sig inom sin budget.")
    else:
        message = "En giltig meny hittades inom en begränsad sökning. Inget näringsdelsteg nådde sin registrerade sökbudget."
    return {
        "status": "VALID_SOLUTION", "global_optimum_proven": False,
        "label": "Lägsta hittade inköpskostnad inom dina val",
        "search_budget": {
            "scope": "current_planner_search_diagnostics",
            "nutrition_status": status,
            "nutrition_searches_recorded": len(nutrition),
            "nutrition_searches_omitted": omitted,
            "nutrition_budget_exhausted_recorded": exhausted,
            "week_search_method": "bounded_beam",
            "distinct_week_proposals_pruned": pruned,
        },
        "budget_message": message + " Globalt lägsta pris är inte bevisat.",
    }


def product_form_compatible(recipe, name, product, fact):
    """Apply raw/dry/drained boundaries even without a nutrition target.

    Existing semantic matching remains authoritative; this only tightens it for
    the explicit input form in an immutable authored recipe.
    """
    if not getattr(recipe, "design", None):
        return True
    from app.services.ingredient_normalizer import canonicalize_ingredient_name

    canonical = canonicalize_ingredient_name(name)
    form = recipe.preparation.input_forms.get(canonical)
    if not form or (product.purchase_terms and product.purchase_terms.identity_scope == "campaign_group"):
        return False
    text = product.name.casefold()
    composition = " ".join(fact.ingredients).casefold() if fact else ""
    if fact and fact.conflicts:
        return False
    ingredient = next((i for i in getattr(recipe, "ingredients", ()) if canonicalize_ingredient_name(i.name) == canonical), None)
    requirements = getattr(ingredient, "product_requirements", None) or ()
    if not _whole_food_identity(canonical, form, product, fact, requirements):
        return False
    if not _requirements_compatible(canonical, requirements, product, fact):
        return False
    if form == "raw_edible" and re.search(r"torkad|pulver|granulat|kokt|grillad|stekt|panerad|nugget|rökt|gravad|rimmad|marinerad", text):
        return False
    if form == "dry" and (re.search(r"kokt|färdig|konserv|avrun", text) or "vatten" in composition):
        return False
    if form in {"cooked_drained", "preserved_drained"}:
        return bool(fact and any(e.get("basis") == "drained" and e.get("unit") == "g"
                                and e.get("quantity") == product.usable_quantity and e.get("source")
                                for e in fact.field_sources.get("usable_quantity", ())))
    return True


def _requirements_compatible(canonical, requirements, product, fact):
    from app.services.content_pack_requirements import compatible
    pack = [r.removeprefix("pack:") for r in requirements if r.startswith("pack:")]
    if pack and not compatible(pack, product, fact):
        return False
    requirements = tuple(r for r in requirements if not r.startswith("pack:"))
    text = product.name.casefold()
    composition = " ".join(fact.ingredients).casefold() if fact else ""
    if set(requirements) - {"plain", "ground", "firm", "thick", "pure_juice", "frozen", "red_split", "white_rice", "white_beans", "dried_leaf"}:
        return False
    if "white_beans" in requirements and not re.search(r"\bvita\b", text + " " + composition):
        return False
    if "ground" in requirements:
        if re.search(r"\bhel(?:a)?\b|stång|stänger", text):
            return False
        if not (re.search(r"malen|pulver", text + " " + composition) or canonical in {"paprikapulver", "chilipulver", "gurkmeja", "cayennepeppar"}):
            return False
    if "firm" in requirements and not re.search(r"\bfast\b|\bfirm\b", text):
        return False
    if "thick" in requirements:
        fat_label = re.search(r"(\d+(?:[,.]\d+)?)\s*%", text)
        fat = float(fat_label.group(1).replace(",", ".")) if fat_label else None
        if fat is None and fact and fact.nutrition_unit == "g" and fact.nutrition_preparation == "as_sold":
            fat = fact.nutrition.get("fat_g")
        if not re.search(r"grekisk|turkisk|avrunnen|strained", text) or fat is None or not 5 <= fat <= 10:
            return False
    if "pure_juice" in requirements and not plain_juice_composition(canonical, composition):
        return False
    if ("plain" in requirements and canonical == "jordnötssmör"
            and not plain_peanut_composition(composition)):
        return False
    if ("frozen" in requirements
            and not re.search(r"fryst|frysta|djupfryst", text + " " + (getattr(product, "category", None) or "").casefold())
            and not _retained_classification(product, fact, "frozen")):
        return False
    if "red_split" in requirements:
        if not re.search(r"röd", text + " " + composition) or re.search(r"gröna|svarta|hela", text + " " + composition):
            return False
        # Red lentils are often split but whole red lentils also exist. An
        # explicit split/peeled source description is required for this method.
        if not (re.search(r"delade|split|skalade", text + " " + composition)
                or _supplier_classification(product, fact, "red_split")):
            return False
    if "white_rice" in requirements:
        if re.search(r"fullkorn|råris|brunt|svart|rött|vildris", text + " " + composition):
            return False
        if not re.search(r"vitt|white|jasmin|basmati|parboiled|långkorn", text + " " + composition):
            return False
    return True


def _supplier_classification(product, fact, value):
    """A culinary declaration must be bound to this source product and pack."""
    if not fact or value not in getattr(fact, "product_classification", ()):
        return False
    provenance = getattr(product, "source_provenance", None)
    if provenance is None:
        return False
    for source in fact.field_sources.get("product_classification", ()):
        if (source.get("identity_method") in {
                "exact_checksum_gtin_brand_fixed_package",
                "unique_exact_complete_brand_variant_fixed_pack"}
                and source.get("bound_product_id") == product.product_id
                and source.get("bound_store_id") == product.store_id
                and source.get("bound_snapshot_id") == provenance.source_snapshot_id
                and source.get("source_package_quantity") == product.package_quantity
                and source.get("source_package_unit") == product.package_unit
                and (source.get("source") or source.get("url"))
                and (source.get("sha256") or source.get("document_sha256"))):
            return True
    return False


def _retained_classification(product, fact, value, *, raw_fields=None):
    if not fact or value not in getattr(fact, "product_classification", ()):
        return False
    provenance = getattr(product, "source_provenance", None)
    if provenance is None:
        return False
    return any(source.get("identity_method") == "hash_verified_retained_product_fields"
               and source.get("value") == value
               and source.get("product_id") == product.product_id
               and source.get("snapshot_id") == provenance.source_snapshot_id
               and source.get("source") == fact.source
               and source.get("raw_fields")
               and (raw_fields is None or all(source["raw_fields"].get(k) == v
                                              for k, v in raw_fields.items()))
               for source in fact.field_sources.get("product_classification", ()))


def _whole_food_identity(canonical, form, product, fact, requirements=()):
    """Whole-product label and declared form, never a substring suggestion.

    This is an additional culinary filter after source identity retrieval. The
    shared matcher, exact quantity checks, allergy checks and pricing gates still
    run afterwards. Unknown variants are not promoted by this filter.
    """
    label = " ".join(product.name.casefold().split())
    category = (getattr(product, "category", None) or "").casefold()
    # Strip only a published brand and package amount, never flavour or method.
    brand = " ".join((getattr(product, "brand", None) or "").casefold().split())
    if brand and label.startswith(brand + " "):
        label = label[len(brand) + 1:]
    label = re.sub(r"\b\d+(?:[,.]\d+)?\s*(?:kg|g|ml|cl|l)\b", "", label)
    label = " ".join(label.split())
    composition = " ".join(fact.ingredients).casefold() if fact else ""
    declared = re.split(r"kan innehålla|kan indeholde|may contain", composition)[0]
    if re.search(r"chips|kex|dipp|buljong|kryddblandning|mariner|smaksatt|nugget|färdigrätt|färdigmat|torrfoder", label):
        return False
    fresh = any(k in category for k in ("frukt", "grönt", "grönsak", "kryddväxt")) or bool(re.search(r"klass [12]|färsk|kruka|knippe", label))
    frozen = bool(re.search(r"fryst|frysta|djupfryst", label + " " + category)) or _retained_classification(product, fact, "frozen")
    herbs = {"dill": r"dill", "persilja": r"(?:persilja|bladpersilja)", "basilika": r"basilika", "koriander": r"koriander", "grönmynta": r"grönmynta"}
    common = r"(?:eko|ekologisk|ekologiskt|ekologiska|svensk|svenska|sverige|klass [12]|krav|färsk|färska|fryst|frysta|djupfryst|djupfrysta|finhackad|hackad|i ask|i påse|påse|kruka|i kruka|knippe|i knippe|blad|krus|hel|hela|skivad|skivade)"
    def simple(pattern, extra=""):
        descriptor = f"(?:{common}|{extra})" if extra else common
        return bool(re.fullmatch(rf"(?:{descriptor} )*{pattern}(?: {descriptor})*", label))
    if canonical in herbs:
        return (form == "raw_edible" and simple(herbs[canonical]) and (fresh or frozen)
                and not re.search(r"\b(?:salt|socker|olja|smör|grädde|vitlök)\b", declared))
    if canonical == "oregano":
        return (form == "dry" and simple("oregano", "torkad|burk") and not fresh and not frozen
                and ("krydd" in category or re.search(r"torkad|burk|påse", label)))
    spices = {"paprikapulver": r"paprikapulver", "spiskummin": r"spiskummin", "chilipulver": r"chilipulver", "cayennepeppar": r"cayennepeppar", "gurkmeja": r"gurkmeja", "kanel": r"(?:kanel|kanel cassia)"}
    if canonical in spices:
        if not (form == "dry" and simple(spices[canonical], "malen|milt|mild|söt|stark|burk") and not fresh):
            return False
        if canonical == "chilipulver":
            # Swedish 'chilipulver' frequently denotes a cumin/salt mixture.
            # Plain powdered chili requires a complete single-ingredient label.
            return bool(fact and fact.ingredients_complete and re.fullmatch(r"(?:ingredienser[: ]*)?(?:chili|chilipeppar)(?:pulver)?[ .%\d,]*", composition))
        return not (composition and re.search(r"\b(?:salt|socker|vitlök|lök|selleri|senap|soja|mjölk)\b", composition.split("kan innehålla")[0]))
    produce = {
        "potatis": r"(?:potatis|färskpotatis|delikatesspotatis|mandelpotatis|minipotatis)",
        "tomat": r"(?:tomat|tomater|körsbärstomater|kvisttomater|plommontomater|cocktailtomater|pärltomater)",
        "vitlök": r"vitlök", "gul lök": r"(?:gul lök|lök gul)", "rödlök": r"(?:rödlök|röd lök)",
        "gurka": r"gurka", "morot": r"(?:morot|morötter)", "zucchini": r"(?:zucchini|squash)",
        "aubergine": r"aubergine", "paprika": r"paprika", "vitkål": r"vitkål", "broccoli": r"broccoli",
        "blomkål": r"blomkål", "champinjoner": r"champinjoner", "selleri": r"(?:selleri|stjälkselleri|blekselleri|bladselleri)",
        "haricots verts": r"haricots verts", "pepparrot": r"pepparrot", "ingefära": r"ingefära",
        "spenat": r"(?:spenat|babyspenat)",
        "rödbeta": r"(?:rödbeta|rödbetor)", "sötpotatis": r"sötpotatis",
    }
    if canonical in produce:
        if not simple(produce[canonical], "fast|mjölig|tvättad|kok|stor|smått&gott|små|delikatess|libanesisk|grön|röd|gul|orange|lila|buketter|blad|ofilmad|i kapsel|skivor"):
            return False
        if re.search(r"\b(?:salt|socker|olja|smör|grädde|ättika|lag)\b", composition.split("kan innehålla")[0]):
            return False
        return not re.search(r"konserv|tork|krydd", category) or fresh
    proteins = {
        "kyckling": r"(?:kycklingfilé|kycklingbröstfilé|kycklingbröst|kyckling lårfilé|kycklinglårfilé|kyckling innerfilé|kycklinginnerfilé|kyckling bröstfilé|kyckling filé)",
        "nötfärs": r"nötfärs", "fläskfärs": r"fläskfärs", "blandfärs": r"blandfärs", "fläskkött": r"(?:fläskfilé|fläskytterfilé|fläskkarré benfri|benfri fläskkarré)",
        "lax": r"(?:laxfilé|laxfile|lax filé|lax)", "fisk": r"(?:torsk|torskfilé|sejfilé|koljafilé|alaska pollock|alaska pollockfilé|torskrygg)",
    }
    if canonical in proteins:
        return (form == "raw_edible" and simple(proteins[canonical], r"benfri|skinnfri|utan skinn|utan ben|portionsbitar|bitar|naturell|strimlad|tärnad|fetthalt lägre än \d+%|\d+(?:[,.]\d+)?\s*%|naturbeteskött")
                and not re.search(r"\b(?:salt|socker|marinad|kryddor|vatten)\b", composition.split("kan innehålla")[0]))
    if canonical in {"yoghurt", "yoghurt naturell"}:
        return bool(re.fullmatch(r"(?:(?:mild|lätt|grekisk|turkisk|laktosfri|ekologisk|eko|naturell) )*yoghurt(?: (?:mild|lätt|naturell|laktosfri|ekologisk|eko|\d+(?:[,.]\d+)?\s*%))*", label)
                    and "naturell" in label and not re.search(r"socker|sirap|vanilj|jordgubb|banan|kokos", declared))
    if canonical == "tofu":
        return bool(re.fullmatch(r"(?:(?:naturell|fast|extra fast|ekologisk|eko) )*tofu(?: (?:naturell|fast|extra fast|firm|ekologisk|eko|vegansk|vegan))*", label.replace("/", " ")) and "naturell" in label and not re.search(r"rök|vitlök|ingefära|chili|marinad|socker", declared))
    if canonical == "keso":
        return bool(re.fullmatch(r"(?:keso|keso cottage cheese|cottage cheese)(?: (?:mini|laktosfri|naturell|ekologisk|eko|\d+(?:[,.]\d+)?\s*%))*", label))
    if canonical == "sojasås":
        return bool(re.fullmatch(r"(?:(?:glutenfri|japansk|tamari) )*sojasås(?: (?:japansk|tamari|glutenfri|vegan))*", label))
    if canonical == "jordnötssmör":
        return bool(re.fullmatch(r"(?:(?:peanut butter|crunchy|smooth|creamy) )*jordnötssmör(?: (?:crunchy|crunch|smooth|creamy|super chunk|eko|ekologiskt))*", label))
    # Established semantic rules already distinguish the remaining canonical
    # staples. Add complete-label boundaries for compound branded alternatives.
    staples = {
        "fetaost": r"fetaost(?: block| original| laktosfri| eko| ekologisk| \d+%)*",
        "ost": r"(?:ost|hårdost|hushållsost|prästost|herrgårdsost|grevé|parmesan|parmigiano reggiano)(?: lagrad| mild| mellanlagrad| riven| skivad| eko| ekologisk| \d+%)*",
        "crème fraiche": r"(?:lätt )?crème fraiche(?: laktosfri| eko| ekologisk| \d+%)*",
        "rapsolja": r"rapsolja(?: kallpressad| eko| ekologisk| d-vitaminberikad)*",
        "citronjuice": r"citronjuice(?: eko| ekologisk| från koncentrat)*",
        "limejuice": r"limejuice(?: eko| ekologisk| från koncentrat)*",
        "krossade tomater": r"(?:krossade tomater|tomater krossade)(?: eko| ekologiska| finkrossade)*",
        "tomatpuré": r"tomatpuré(?: dubbelkoncentrerad| eko| ekologisk)*",
        "kokosmjölk": r"kokosmjölk(?: eko| ekologisk| original)*",
        "sesamfrön": r"sesamfrön(?: vita| skalade| oskalade| eko| ekologiska| burk)*",
        "senap": r"(?:dijon )?senap(?: dijon| stark| mild| grov| skånsk| sötstark| finmalen)*",
        "kapris": r"kapris(?: små| fina| fin| i lag)*", "oliver": r"(?:gröna |svarta )?oliver(?: utan kärnor| urkärnade| kalamata| gröna| svarta| eko| ekologiska)*",
        "salt": r"(?:salt|hushållssalt|finkornigt salt)(?: med jod| utan jod| fint| finkornigt)*",
        "mjölk": r"(?:standardmjölk|mellanmjölk|lättmjölk|mjölk)(?: laktosfri| ekologisk| eko| \d+(?:[,.]\d+)?\s*%)*",
    }
    if canonical in staples:
        return bool(re.fullmatch(staples[canonical], label))
    grains = {
        "ris": r"(?:ris|jasminris|basmatiris|långkornigt ris|parboiled ris)",
        "pasta": r"(?:pasta|spaghetti|spagetti|penne|fusilli|makaroner|tagliatelle|rigatoni|farfalle|linguine|orecchiette)",
        "nudlar": r"(?:äggnudlar|nudlar|risnudlar)", "couscous": r"couscous",
        "linser": r"(?:röda linser|linser röda|linser)", "vetemjöl": r"(?:vetemjöl|kärnvetemjöl)",
        "havregryn": r"(?:havregryn|fina havregryn)", "ströbröd": r"(?:ströbröd|panko|panko ströbröd)",
    }
    if canonical in grains:
        if canonical == "pasta" and "pack:small_pasta" in requirements:
            return form == "dry" and simple(r"(?:risoni|kritharaki|orzo)", "original|durumvete|durum")
        return form == "dry" and simple(grains[canonical], "fullkorn|fullkorns|glutenfri|glutenfritt|snabb|original|durumvete|durum|malet|fint|finmalet|special|siktat|torkade|delade|skalade|split")
    legumes = {"kikärtor": "kikärtor|kikärter", "kidneybönor": "kidneybönor|röda kidneybönor", "svarta bönor": "svarta bönor", "bönor": "bönor|vita bönor|stora vita bönor|vita bönor stora", "majs": "majs|majskorn|sockermajs", "ärtor": "ärtor|gröna ärtor"}
    if canonical in legumes:
        return simple(f"(?:{legumes[canonical]})", "kokta|avrunna|sweet corn|extra fina|söta|2-p|3-pack|utan tillsatt socker")
    if canonical == "tortillas":
        return bool(re.fullmatch(r"(?:(?:street|corn|glutenfria|glutenfri) )*(?:tortilla|tortillas|vetetortilla|vetetortillas)(?: original| medium| large| small| fullkorn| vete| majs| soft| mini| wraps| glutenfri| glutenfria| ekologiska| eko)*", label))
    if canonical == "bröd":
        if (form != "as_sold" or _retained_classification(product, fact, "not_ready_plain_bread")
                or _retained_classification(product, fact, "frozen")
                or (composition and not plain_bread_composition(composition))):
            return False
        if re.fullmatch(r"(?:bröd|fullkornsbröd|surdegsbröd|rågbröd|formbröd|rostbröd|lantbröd|pitabröd)(?: fullkorn| grovt| ljust| mörkt| skivat| skivor| original| vete| råg| ekologiskt| eko)*", label):
            return True
        return bool(fact and len(fact.ingredients) == 1 and plain_bread_composition(composition)
                    and _retained_classification(product, fact, "ready_baked_bread", raw_fields={
                        "name": product.name, "listOfIngredients": fact.ingredients[0]}))
    from app.services.content_pack_requirements import additional_whole_identity
    return additional_whole_identity(canonical, form, label, composition)


def _culinary_words(composition):
    # This parses a stated culinary formula. It does not assert that retailer
    # source coverage is complete enough to prove allergen absence. Preserve
    # the original declaration and its separate ingredients_complete flag.
    declared = re.split(r"kan innehålla|kan indeholde|may contain|förvaras|förvaring", composition.casefold())[0]
    return set(re.findall(r"[^\W\d_]+", declared)), declared


def plain_juice_composition(canonical, composition):
    # Origin and certification are not extra ingredients. Remove only these
    # explicit metadata shapes, preserving every token of the actual formula.
    fruit = {"citronjuice": "citron", "limejuice": "lime"}.get(canonical)
    if fruit is None:
        return False
    source = composition.casefold()
    source = re.sub(rf"\({fruit}: (?:eu \()?[^()]+\)?\)", "", source)
    source = re.split(r"\*+krav-ekologisk ingrediens\.", source)[0]
    words, declared = _culinary_words(source)
    allowed = {canonical, "ingredienser", "juice", "från", "koncentrat", "framställd", "framställt", "av", "vatten",
               "antioxidationsmedel", "konserveringsmedel", "kaliummetabisulfit", "kaliumdisulfit", "svaveldioxid",
               "natriumbensoat", "e", "citronsyra", "sulfit", "ekologisk", "pastöriserad", "inte"}
    if not words or canonical not in words or not words <= allowed:
        return False
    if "vatten" in words and "från koncentrat" not in declared:
        return False
    fraction = re.search(r"juice\s*\(?\s*(\d+(?:[,.]\d+)?)\s*%", declared)
    return fraction is None or float(fraction.group(1).replace(",", ".")) >= 99


def plain_peanut_composition(composition):
    words, _ = _culinary_words(composition)
    allowed = {"ingredienser", "jordnötter", "jordnöt", "jordnötssmör", "rostade", "malda", "och", "ekologiska",
               "ekologisk", "salt", "havssalt", "kina", "argentina", "ursprung", "eu", "icke"}
    return bool(words & {"jordnötter", "jordnöt"}) and words <= allowed


def plain_bread_composition(composition):
    """A reviewed plain cereal formula; this does not prove allergen absence."""
    words, declared = _culinary_words(composition)
    flours = {"vetemjöl", "rågmjöl", "fullkornsvetemjöl", "fullkornsrågmjöl", "havremjöl",
              "kornmjöl", "dinkelmjöl", "durumvetemjöl"}
    allowed = flours | {"ingredienser", "vatten", "jäst", "surdeg", "surdegspulver", "vete", "råg",
        "korn", "havre", "dinkel", "malt", "vetemalt", "rågmalt", "kornmalt", "maltmjöl",
        "rågkärnor", "vetekärnor", "havregryn", "vetegluten", "gluten", "fullkorn", "fullkorns",
        "socker", "sirap", "rapsolja", "solrosolja", "olivolja", "salt", "havssalt",
        "mjölbehandlingsmedel", "askorbinsyra", "enzym", "enzymer", "av", "och",
        "grovt", "grova", "klippta", "krossade", "fermenterat", "siktat", "torkad", "torkat",
        "ekologisk", "ekologiskt", "ekologiska"}
    first = re.sub(r"^\s*ingredienser\s*:?\s*", "", declared)
    first = re.sub(r"^ekologisk(?:t|a)?\s+", "", first)
    first_word = re.match(r"[^\W\d_]+", first)
    return bool(words <= allowed and words & flours and "vatten" in words
                and words & {"jäst", "surdeg", "surdegspulver"}
                and first_word and first_word[0] in flours | {"vatten"})


def pantry_form_compatible(item, row):
    """Generic stock needs user-confirmed form; exact stock uses resolved keys."""
    form = item.get("form")
    if form is None and item.get("nutrition_reference"):
        from app.services.nutrition_reference import MAPPINGS, validate_pantry_reference
        try:
            identity = validate_pantry_reference(item["name"], item["unit"], item["nutrition_reference"])
            reference_form = MAPPINGS[identity][1]
            form = ("raw_edible" if reference_form.startswith("raw") else
                    "cooked_drained" if reference_form == "drained" else
                    "dry" if reference_form == "dry" else
                    "as_sold" if reference_form in {"ready", "canned_with_liquid", "frozen"} else None)
        except (ValueError, KeyError):
            return False
    if form != row.get("input_form"):
        return False
    from types import SimpleNamespace
    category = "frukt och grönsaker" if form == "raw_edible" else "kryddor" if form == "dry" else ""
    if not _whole_food_identity(row["name"], form, SimpleNamespace(name=item["name"], category=category), None):
        return False
    return _requirements_compatible(row["name"], row.get("product_requirements", ()),
        SimpleNamespace(name=item["name"], category=category), None)
