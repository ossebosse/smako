"""Smako account entitlement, independent of grocery loyalty programs."""

from fastapi import HTTPException

GUEST_RECIPES = 3
GUEST_SERVINGS = 2


def require_membership_limits(plan, request):
    from app.api.account import verified_owner

    if verified_owner(request):
        return
    if plan.personal is None:
        count = plan.recipes
        servings = [plan.servings] if count else []
    else:
        count = sum(meal.count for meal in plan.personal.meals)
        servings = [meal.servings for meal in plan.personal.meals if meal.count]
        servings += [slot.recipe.servings for slot in plan.personal.slots or [] if slot.recipe]
    if count > GUEST_RECIPES or any(value > GUEST_SERVINGS for value in servings):
        raise HTTPException(
            403,
            "Som gäst kan du skapa högst 3 recept per meny och 2 portioner per recept. "
            "Skapa ett konto eller logga in för fler recept och portioner.",
            headers={"X-Error-Code": "membership_required", "Cache-Control": "private, no-store"},
        )
