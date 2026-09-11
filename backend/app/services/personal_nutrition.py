"""Reviewed, narrow nutrition calculation grounds; no generated retention factors.

The cold preparations below serve the measured edible ingredients without heat,
draining or added oil. Declared as-sold macros can therefore be summed. This is
a label-based estimate, not a laboratory measurement of the served meal.
Changing instructions or ingredient forms requires a new supported ground.
"""

from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.personal_policy import PolicyConflict

VERSION = "cold-edible-assembly-v1"


def requested_nutrients(limits):
    return {
        k.removeprefix("min_").removeprefix("max_")
        for k, v in limits.model_dump().items()
        if v is not None
    } - {"weight_g"}


def calculation_basis(recipe):
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
        )
    return {
        "version": VERSION,
        "description": "Uppskattning från produktdeklarationer för uppmätta ätbara ingredienser, serverade utan värmning eller avrinning. Ingen tillagad vikt eller hållbarhet är verifierad.",
        "method": "sum_declared_edible_as_sold",
        "retention_factors": "not_needed_cold_assembly",
    }
