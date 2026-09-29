"""Reviewed, narrow nutrition calculation grounds; no generated retention factors.

The cold preparations below serve the measured edible ingredients without heat,
draining or added oil. Declared as-sold macros can therefore be summed. This is
a label-based estimate, not a laboratory measurement of the served meal.
Changing instructions or ingredient forms requires a new supported ground.
"""

from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.personal_policy import PolicyConflict

VERSION = "cold-edible-assembly-v1"


def raw_salad_instructions():
    return [
        "Skölj grönsaker och färska korianderblad. Skala vitlöken om den ingår. Avlägsna oätliga delar före vägning; använd inte torkade kryddor, inlagda grönsaker eller färdiga såser.",
        "Väg endast de ätbara mängderna i ingredienslistan i gram. Hacka och blanda råa; behåll all saft. Ingen värmning, avrinning, olja eller olistad ingrediens ingår.",
        "Servera hela den uppmätta blandningen jämnt fördelad mellan portionerna. Förpackningsrester och borttagna delar ingår inte i näringsberäkningen.",
    ]


def is_raw_salad_preparation(recipe):
    if recipe is None:
        return False
    names = {canonicalize_ingredient_name(i.name) for i in recipe.ingredients}
    return bool(names and names <= {'tomat', 'gurka', 'koriander', 'vitlök'}
                and len(names) == len(recipe.ingredients)
                and all(i.unit == 'g' for i in recipe.ingredients)
                and recipe.instructions == raw_salad_instructions())


def couscous_instructions():
    return [
        "Väg upp torr vanlig couscous av durumvete, naturell fast tofu som såld utan lag och tvättade råa tomater enligt ingredienslistan. Använd inte pärlcouscous, smaksatta gryn eller silkestofu. Ingen pressning eller avrinning av tofun ingår.",
        "Lägg couscous i en skål. Tillsätt kokhett dricksvatten enligt förpackningens anvisning för svällning, täck och låt svälla tills grynen är mjuka. Allt tillsatt vatten ska absorberas; häll inte av eller skölj grynen. Lufta med gaffel.",
        "Tärna tofun och tomaterna. Vänd ihop med den svällda couscousen till en ljummen sallad. Behåll tomatsaften i salladen. Servera hela den använda mängden fördelad jämnt mellan portionerna, utan tillsatt olja eller andra olistade ingredienser.",
    ]


def is_couscous_preparation(recipe):
    return (
        len(recipe.ingredients) == 3
        and {canonicalize_ingredient_name(i.name) for i in recipe.ingredients}
        == {"tofu", "couscous", "tomat"}
        and all(i.unit == "g" for i in recipe.ingredients)
        and recipe.instructions == couscous_instructions()
    )


def requested_nutrients(limits):
    return {
        k.removeprefix("min_").removeprefix("max_")
        for k, v in limits.model_dump().items()
        if v is not None
    } - {"weight_g"}


def reference_instructions(form):
    common = [
        "Väg de listade mängderna: benfri fiskfilé utan skinn eller kycklingbröstfilé utan skinn, torra äggnudlar eller långkornigt vitt ris och tvättade grönsaker. Moroten används oskalad; vitkålens ätbara delar, även fint skuren stock, används. Kasserade eller oätliga delar ingår inte i den vägda mängden.",
        "Koka ris eller äggnudlar separat enligt förpackningen. Koka morot eller vitkål mjuk i vatten. Använd inget extra fett, salt, kryddor eller andra olistade ingredienser i denna beräknade version.",
        "Sjud fisk eller kyckling varsamt i vatten tills genomlagad. Ta upp råvarorna; kokvattnet används inte som näringskälla. Dela alla angivna råvaror jämnt mellan portionerna.",
    ]
    finish = {
        "plate": "Servera filén hel på tallrik med riset och grönsakerna vid sidan.",
        "soup": "Skär den tillagade filén och grönsakerna i munsbitar. Lägg i portionsskålar med ris eller nudlar, tillsätt hett dricksvatten till en skedbar soppa och servera.",
        "stew": "Dela den tillagade fisken i stora bitar. Mosa hälften av den kokta moroten med lite hett dricksvatten till en tjock bas. Vänd försiktigt ned fisk och resterande morot, värm igenom och servera grytan med riset separat.",
        "fried_plate": "Stek laxfilén på båda sidor i en belagd panna utan extra fett tills genomlagad. Lägg upp filén utan kvarvarande steksky. Servera med kokt ris och morötter vid sidan.",
        "salmon_pan": "Stek laxfilén på båda sidor i en belagd panna utan extra fett tills genomlagad. Lägg upp fisken utan kvarvarande steksky och dela i stora flagor. Vänd ihop med kokta äggnudlar och finstrimlad kokt vitkål; servera som nudelpanna.",
        "cod_pan": "Stek den skinnfria torskfilén varsamt på båda sidor i en belagd panna utan extra fett tills genomlagad. Ta upp fisken utan kvarvarande steksky. Servera med de kokta äggnudlarna och vitkålen.",
    }
    if form in {"fried_plate", "salmon_pan", "cod_pan"}:
        common[2] = (
            "Fördela samtliga angivna råvaror jämnt mellan portionerna. Laxen steks i nästa steg. Den ska inte kokas först; tillsätt inga olistade ingredienser."
        )
        if form == "cod_pan":
            common[2] = common[2].replace("Laxen", "Torsken")
    return common + [finish[form]]


def is_reference_preparation(recipe):
    names = {canonicalize_ingredient_name(i.name) for i in recipe.ingredients}
    return (
        len(names) == len(recipe.ingredients) == 3
        and len(names & {"kyckling", "lax", "fisk"}) == 1
        and len(names & {"ris", "nudlar"}) == 1
        and len(names & {"morot", "vitkål"}) == 1
        and all(i.unit == "g" for i in recipe.ingredients)
        and any(
            recipe.instructions == reference_instructions(form)
            for form in (
                ("plate", "soup", "stew", "fried_plate", "salmon_pan")
                if "lax" in names
                else (
                    ("plate", "soup", "stew", "cod_pan")
                    if "fisk" in names
                    else ("plate", "soup", "stew")
                )
            )
        )
    )


def calculation_basis(recipe, *, allow_estimates=False):
    if recipe.preparation is not None:
        from app.services.recipe_preparation import basis
        if not allow_estimates:
            raise PolicyConflict("Receptets insatsbaserade beredning kräver opt-in för näringsuppskattning.", code="DATA_BLOCKED", stage="preparation")
        try:
            return basis(recipe)
        except ValueError as exc:
            raise PolicyConflict(str(exc), code="DATA_BLOCKED", stage="preparation") from exc
    if allow_estimates and is_raw_salad_preparation(recipe):
        from app.services.nutrition_reference import reference_data
        return {
            'version': reference_data()['content_version'],
            'method': 'sum_measured_raw_edible_input',
            'description': 'Generiska SLV-referenser för uppmätta ätbara råa grönsaker och färska blad, med produktdeklaration där sådan är kvalificerad. Ingen värmning, avrinning, densitet eller ätbar andel av inköpt hel vara antas.',
            'retention_factors': 'not_needed_cold_assembly',
        }
    from app.services.reviewed_cold_meals import VERSION as cold_version
    from app.services.reviewed_cold_meals import preparation as cold_preparation

    if cold_preparation(recipe):
        return {
            "version": cold_version,
            "method": "sum_declared_edible_as_sold",
            "description": "Produktdeklarationer för uppmätt kvarg, bröd och ost som serveras kalla utan avrinning. Ingen densitet, tillagad slutvikt eller förlustfaktor antas.",
            "retention_factors": "not_needed_cold_assembly",
        }
    from app.services.reviewed_warm_meals import basis, preparation

    if allow_estimates and preparation(recipe):
        return basis(recipe)
    if allow_estimates and is_couscous_preparation(recipe):
        from app.services.nutrition_reference import reference_data

        return {
            "version": reference_data()["content_version"],
            "method": "reviewed_rehydration_and_edible_assembly",
            "description": "Uppskattning från använd torr couscous, naturell fast tofu och rå tomat. Redan ångbehandlade gryn sväller i vatten; ingen vätska, tofu eller tomatsaft hälls bort. Makron summeras från använd mängd med produktdeklaration där den är kvalificerad. Vattnet tillför ingen energi. Ingen exakt näringsretention eller tillagad vikt är verifierad.",
            "cooked_weight": "NOT_VERIFIED",
        }
    if allow_estimates and is_reference_preparation(recipe):
        from app.services.nutrition_reference import reference_data

        return {
            "version": reference_data()["content_version"],
            "method": "documented_cooked_component_per_raw_input",
            "description": "Gränser uppfyllda enligt beräkningen med livsmedelsspecifika referenser för kokning eller stekning av lax/torsk. Produktdeklaration används där den är kvalificerad, annars tydligt mappat generiskt värde. Faktisk förlust och slutvikt kan avvika; detta garanterar inte färdiglagad mats exakta innehåll. Inget extra stekfett ingår i dessa recept.",
            "cooked_weight": "NOT_VERIFIED",
        }
    names = {canonicalize_ingredient_name(i.name) for i in recipe.ingredients}
    units = {canonicalize_ingredient_name(i.name): i.unit for i in recipe.ingredients}
    steps = tuple(recipe.instructions)
    approved = (
        (
            steps == ("Skiva osten och lägg på brödet.", "Servera med mjölken.")
            and names == {"ost", "bröd", "mjölk"}
        )
        or (
            steps == ("Skölj och skär moroten i stavar.", "Skär osten i bitar och servera till.")
            and names == {"morot", "ost"}
        )
        or (steps == ("Servera tillsammans.",) and names <= {"bröd", "ost", "mjölk"})
    )
    if not approved or any(u != ("ml" if n == "mjölk" else "g") for n, u in units.items()):
        raise PolicyConflict(
            f"{recipe.name}: näringsberäkning saknar granskad beredningsgrund för värme, avrinning eller ätbar mängd. Produktdeklarationer räcker inte ensamma; inga förlustfaktorer har antagits.",
            code="DATA_BLOCKED",
            stage="preparation",
        )
    return {
        "version": VERSION,
        "description": "Uppskattning från produktdeklarationer för uppmätta ätbara ingredienser, serverade utan värmning eller avrinning. Ingen tillagad vikt eller hållbarhet är verifierad.",
        "method": "sum_declared_edible_as_sold",
        "retention_factors": "not_needed_cold_assembly",
    }


def reference_method(recipe, name):
    if canonicalize_ingredient_name(
        name
    ) == "fisk" and recipe.instructions == reference_instructions("cod_pan"):
        return "fry"
    if canonicalize_ingredient_name(name) == "lax" and any(
        recipe.instructions == reference_instructions(f) for f in ("fried_plate", "salmon_pan")
    ):
        return "fry"
    return "boil"
