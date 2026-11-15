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
