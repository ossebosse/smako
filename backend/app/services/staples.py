"""Basic foods the person says they have at home (owner decision 2026-11-15).

"Har du hemma?" lists a fixed set of everyday staples. A ticked staple is not
bought for recipes: the person's own stock covers the small amounts recipes
use. This is a statement by the person, not a pantry quantity; nothing is
reserved or deducted. See docs/PLANNING-ARCHITECTURE.md.

Exceptions keep every check exact:
- a meal with nutrition limits buys the staple, so its values are declared;
- an ingredient row with allergies buys it, as allergies need a declaration;
- an explicit product choice or extra row is never replaced.
Informational nutrition uses the reviewed generic reference for the staple
when one exists in the same unit; otherwise that recipe shows no values.
"""

from __future__ import annotations

from app.services.ingredient_normalizer import canonicalize_ingredient_name

# Canonical recipe ingredient names, in the order the interfaces show them.
STAPLES = (
    "salt", "svartpeppar", "rapsolja", "olivolja", "strösocker", "vetemjöl",
    "oregano", "timjan", "spiskummin", "paprikapulver", "rökt paprikapulver",
    "kanel", "chiliflakes", "gurkmeja",
)


def is_at_home(name, staples):
    return bool(staples) and canonicalize_ingredient_name(name) in staples


def reference_identity(name, unit):
    """A reviewed generic nutrition reference for the staple, if any."""
    from app.services.nutrition_reference import reference_options

    wanted = canonicalize_ingredient_name(name)
    for option in reference_options():
        if (option["unit"] == unit and option["preparation"] in {"ready", "dry"}
                and canonicalize_ingredient_name(option["ingredient"]) == wanted):
            return option["id"]
    return None


# A staple measured by volume with a reviewed per-gram reference and a
# reviewed density (DTU). Only foods listed here; more need the same review.
_VOLUME_REFERENCES = {"rapsolja": 2189}


def volume_evidence(name, unit):
    """Per-100 ml nutrition for the person's own oil, as for bought oil.

    The SLV per-100 g reference times DTU's reviewed density
    (recipe_volume_nutrition.density_converted). None for anything else.
    """
    if unit != "ml":
        return None
    canonical = canonicalize_ingredient_name(name)
    if canonical not in _VOLUME_REFERENCES:
        return None
    from app.services.nutrition_reference import reference_evidence
    from app.services.recipe_volume_nutrition import density_converted

    return density_converted(reference_evidence(_VOLUME_REFERENCES[canonical]), canonical)


# Owner decisions 2026-11-20/21: informational nutrition never counts dried
# spices (any amount), which Livsmedelsverket often has no values for; a
# teaspoon of spice is a few kcal. The plan names what was left out.
# Nutrition limits still require values for every ingredient.
DRIED_SPICES = frozenset({
    # Canonical names in the recipe library, dried spices and herbs only.
    "svartpeppar", "vitpeppar", "kryddpeppar", "cayennepeppar", "chiliflakes", "paprikapulver",
    "rökt paprikapulver", "spiskummin", "kummin", "oregano", "timjan", "rosmarin", "mejram", "salvia",
    "kanel", "kardemumma", "muskot", "nejlika", "kryddnejlika", "gurkmeja", "malen ingefära",
    "malen koriander", "garam masala", "lagerblad", "fänkålsfrön", "senapsfrön", "saffran", "enbär",
    "vaniljpulver", "torkade makrutlimeblad", "anchochili", "femkryddor",
})


# Owner decision 2026-11-21: fresh mint is left out too; there is no reviewed
# reference for an unnamed mint species.
LEFT_OUT_HERBS = frozenset({"mynta"})


def negligible_spice(name, quantity, unit):
    return (unit == "g" and quantity > 0
            and canonicalize_ingredient_name(name) in DRIED_SPICES | LEFT_OUT_HERBS)
