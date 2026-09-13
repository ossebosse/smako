"""Explicit opt-in estimates for four normal, no-discard weekday preparations.

All measured edible food is served. Water changes concentration, not the sum
of input macros. This is an input-based estimate of the meal, never measured
retention, cooked weight, or a nutritional use of unconsumed package surplus.
"""

from dataclasses import replace

from app.models.recipe import Recipe, RecipeIngredient
from app.services.ingredient_normalizer import canonicalize_ingredient_name

VERSION = "warm-edible-input-review-20260913"
SOURCES = [
    {
        "url": "https://www.livsmedelsverket.se/livsmedel-och-innehall/tillagning-forvaring-hallbarhet/tillagning/hur-paverkas-maten-vid-tillagning/",
        "retrieved_at": "2026-09-13",
        "supports": "Qualitative support: ordinary cooking changes energy-giving nutrients relatively little; liquid can retain leached nutrients. No exact numerical retention factor or cooked yield is inferred.",
    },
    {
        "url": "https://www.livsmedelsverket.se/globalassets/publikationsdatabas/rapporter/2017/2017-nr-21-del-1-naringsforandringar-vid-tillagning-och-forvaring-riskhanteringsrapport.pdf",
        "retrieved_at": "2026-09-13",
        "supports": "Underlying review of nutrient changes; input sum remains explicitly an estimate of these exact preparations, not a measured food value.",
    },
]
TEMPLATES = {
    "lentil_pasta": (
        "Pasta med röd linssås och tomat",
        [("linser", 75), ("pasta", 75), ("krossade tomater", 200), ("morot", 100)],
        [
            "Väg torra röda linser, torr vanlig durumvetepasta, tvättad oskalad morot och krossade tomater med all tomatvätska enligt listan. Riv moroten grovt. Använd inte kokta linser, bönpasta eller färdig pastasås.",
            "Kontrollera och skölj linserna, lägg dem och den rivna moroten i en rymlig kastrull och täck med dricksvatten. Koka på låg värme enligt linsförpackningen tills de är mjuka; häll inte bort kokvätskan. Tillsätt mer vatten vid behov så att de inte kokar torrt.",
            "Rör ned de krossade tomaterna och den torra pastan i linssåsen. Bryt lång pasta så att den ryms. Koka pastan i såsen enligt förpackningens koktid och rör ofta. Tillsätt hett vatten lite i taget tills pastan är mjuk och såsen krämig. Ingen vätska hälls bort.",
            "Servera all pasta med linssås, jämnt fördelad mellan portionerna. Inget extra fett eller andra olistade ingredienser ingår i denna version.",
        ],
    ),
    "tofu_noodle_pan": (
        "Tofupanna med äggnudlar och vitkål",
        [("tofu", 150), ("nudlar", 80), ("vitkål", 150)],
        [
            "Väg naturell fast tofu som såld utan lag, torra äggnudlar och tvättad, fint strimlad ätbar vitkål enligt listan. Ingen pressning eller avrinning av tofun ingår.",
            "Tärna tofun. Stek tofun och vitkålen varsamt i en rymlig belagd panna utan extra fett. Vänd ofta och tillsätt en skvätt dricksvatten om något fastnar; behåll allt i pannan.",
            "Lägg i de torra äggnudlarna och häll i hett dricksvatten lite i taget. Koka under lock enligt nudlarnas anvisning, vänd och fyll på vatten tills nudlarna är mjuka. Lyft av locket och låt överflödigt vatten ånga bort; häll inte bort vätska eller mat.",
            "Vänd ihop allt till en nudelpanna och fördela hela den använda mängden jämnt mellan portionerna. Inga andra olistade ingredienser ingår.",
        ],
    ),
    "lentil_rice_stew": (
        "Röd linsgryta med tomat och ris",
        [("linser", 85), ("ris", 60), ("krossade tomater", 200), ("morot", 100)],
        [
            "Väg torra röda linser, torrt långkornigt vitt ris, tvättad oskalad morot och krossade tomater med all tomatvätska enligt listan. Skär moroten i små tärningar. Använd inte kokta linser, fullkornsris eller smaksatta risblandningar.",
            "Kontrollera och skölj linserna. Lägg dem och morotstärningarna i en kastrull med dricksvatten och sjud enligt linsförpackningens anvisning tills allt är mjukt. Häll inte av kokvätskan. Rör ned tomaterna och låt puttra till en tjock linsgryta; späd med vatten om det behövs.",
            "Koka riset separat i uppmätt dricksvatten enligt förpackningens absorptionsmetod. All vätska ska tas upp eller ånga bort; häll inte av eller skölj det kokta riset.",
            "Servera den tjocka linsgrytan med riset vid sidan. Fördela alla använda ingredienser jämnt mellan portionerna. Inget extra fett eller andra olistade ingredienser ingår.",
        ],
    ),
    "chicken_oven": (
        "Ugnsbakad kyckling med morötter och ris",
        [("kyckling", 150), ("ris", 80), ("morot", 150)],
        [
            "Värm ugnen till 200 grader. Väg rå kycklingbröstfilé utan skinn och ben, torrt långkornigt vitt ris och tvättad oskalad morot enligt listan. Använd omörad kyckling utan saltlake eller marinad. Skär kycklingen i jämna strimlor och moroten i tunna stavar.",
            "Lägg kyckling och morot i en ugnsform med en bottenskyla dricksvatten. Täck med lock eller folie och baka i ugnen tills kycklingen är helt genomlagad och moroten mjuk, cirka 25–30 minuter. Kontrollera kycklingens genomstekning; fortsätt tillagningen vid behov. Behåll all sky i formen.",
            "Koka riset enligt förpackningens absorptionsmetod i uppmätt dricksvatten. Låt all vätska absorberas eller ånga bort; häll inte av eller skölj efter kokningen.",
            "Servera den ugnsbakade kycklingen och morötterna med riset. Skeda all genomhettad sky över maten och fördela alla angivna råvaror jämnt mellan portionerna. Inget extra fett eller andra olistade ingredienser ingår.",
        ],
    ),
}


def candidates(servings=4):
    return [
        Recipe(
            name=name,
            servings=servings,
            ingredients=[
                RecipeIngredient(name=n, quantity=q * servings, unit="g") for n, q in ingredients
            ],
            instructions=instructions,
        )
        for name, ingredients, instructions in TEMPLATES.values()
    ]


def preparation(recipe):
    if recipe is None:
        return None
    for key, (_, ingredients, instructions) in TEMPLATES.items():
        if (
            recipe.instructions == instructions
            and len(recipe.ingredients) == len(ingredients)
            and {canonicalize_ingredient_name(i.name) for i in recipe.ingredients}
            == {i[0] for i in ingredients}
            and all(i.unit == "g" for i in recipe.ingredients)
        ):
            return key
    return None


def basis(recipe):
    return {
        "version": VERSION,
        "recipe_review": preparation(recipe),
        "method": "reviewed_warm_edible_input_sum",
        "description": "Uppskattning från uppmätt använd rå/torr/ätfärdig insats. All mat och kokvätska serveras; vatten kan avdunsta. Produktdeklaration används där kvalificerad, annars explicit SLV-referens. Ingen exakt näringsretention eller tillagad vikt är verifierad; förpackningsrest ingår inte.",
        "cooked_weight": "NOT_VERIFIED",
        "sources": SOURCES,
    }


def evidence(identity, recipe, declaration=None):
    from app.services.nutrition_reference import reference_evidence

    allowed = {
        "lentil_pasta": {884, 845, 422, 289},
        "tofu_noodle_pan": {905, 870, 370},
        "lentil_rice_stew": {884, 2481, 422, 289},
        "chicken_oven": {1173, 2481, 289},
    }
    key = preparation(recipe)
    if identity not in allowed.get(key, set()):
        return None
    ref = reference_evidence(identity)
    values = declaration.nutrition if declaration else ref.nutrition
    sources = declaration.field_sources if declaration else ref.field_sources
    return replace(
        ref,
        nutrition=values,
        source=declaration.source if declaration else ref.source,
        source_product_id=declaration.source_product_id if declaration else ref.source_product_id,
        evidence_kind="reviewed_warm_input_estimate",
        nutrition_basis=(declaration.nutrition_basis if declaration else ref.nutrition_basis)
        + " "
        + basis(recipe)["description"],
        field_sources={
            f"nutrition.{k}": tuple(sources.get(f"nutrition.{k}", ()))
            + (
                {
                    "kind": "reviewed_warm_input_estimate",
                    "review": VERSION,
                    "recipe_review": key,
                    "food_id": identity,
                    "operation": "as_sold_macros * used_edible_input_g / 100",
                    "discarded_food_g": 0,
                    "cooked_quantity_g": None,
                    "package_surplus_included": False,
                },
            )
            for k in values
        },
    )
