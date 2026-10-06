"""Owned guest workspace, bound to the existing HttpOnly capability."""

from __future__ import annotations

import hashlib
import json

from app.api.beta_ops import _require_same_origin
from app.api.plan import (
    _pending_plan_job,
    _plan_actor_hash,
    _plan_jobs,
    _planner_admission_key,
    _run_personal_thread,
    _run_personal_work,
    _store,
    _with_release,
)
from app.config import get_settings
from app.models.personal import (
    PantryWrite,
    PersonalMutation,
    PersonalPlanning,
    ProfileWrite,
    TasteProfile,
)
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import (
    PolicyConflict,
    interpret_profile,
    interpretation,
    pantry_checks,
)
from app.services.personal_store import PersonalConflict, PersonalStore, available_items
from app.services.plan_store import PlanNotFoundError, PlanOwnerMismatchError, PlanReadOnlyError
from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

router = APIRouter(prefix="/api/personal", tags=["private planning"])


@router.get("/nutrition-references")
def nutrition_references():
    from app.services.nutrition_reference import reference_data, reference_options

    data = reference_data()
    return {
        "version": data["content_version"],
        "options": reference_options(),
        "source": data["source"],
        "license": data["license"],
    }


class TextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(max_length=2000)


def context(request, response):
    settings = get_settings()
    _require_same_origin(request, settings)
    response.headers["Cache-Control"] = "private, no-store"
    store = _store(request)
    return settings, store, _plan_actor_hash(request, settings)


def public_state(state, request=None, profile=None):
    from app.api.account import status

    return {
        "revision": state["revision"],
        "profile": state["profile"],
        "items": available_items(state),
        "reservations": state["reservations"],
        "events": state["events"],
        "ledger": state.get("ledger", []),
        "account": status(request),
        "pantry_checks": pantry_checks(
            state["items"], profile or TasteProfile.model_validate(state["profile"] or {})
        ),
    }


@router.get("/state")
def state(request: Request, response: Response):
    _settings, plans, owner = context(request, response)
    return public_state(PersonalStore(plans).read(owner), request)


@router.post("/interpret-profile")
def profile_interpret(payload: TextInput, request: Request, response: Response):
    context(request, response)
    return interpret_profile(payload.text)


@router.post("/interpret-extra")
def extra_interpret(payload: TextInput, request: Request, response: Response):
    context(request, response)
    return {
        "query": payload.text.strip(),
        "properties": interpretation(payload.text),
        "confirmed": False,
    }


@router.put("/pantry")
def pantry_update(payload: PantryWrite, request: Request, response: Response):
    _settings, plans, owner = context(request, response)
    if any(item.product_key for item in payload.items):
        prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request("22350", {})
        if prepared is None:
            raise PolicyConflict(
                "Exakta skafferivaror kräver lokalt produktunderlag.", code="DATA_BLOCKED"
            )
        for item in payload.items:
            if not item.product_key:
                continue
            positions = prepared.product_search_index.groups.get(item.product_key, ())
            if not positions:
                raise PolicyConflict(
                    "Den exakta skafferiprodukten saknas i underlaget. Behåll tidigare lager eller lägg till en generisk vara uttryckligen.",
                    code="DATA_BLOCKED",
                )
            product = prepared.universe.products[positions[0]]
            if product.usable_unit and item.unit != product.usable_unit:
                raise PolicyConflict(
                    f"{product.name}: verifierad lagerenhet är {product.usable_unit}; ingen omräkning till {item.unit} finns."
                )
            item.name = product.name
    return public_state(
        PersonalStore(plans).update_pantry(owner, payload.revision, payload.items),
        request,
        payload.profile,
    )


@router.put("/profile")
def profile_update(payload: ProfileWrite, request: Request, response: Response):
    _settings, plans, owner = context(request, response)
    return public_state(
        PersonalStore(plans).update_profile(owner, payload.revision, payload.profile), request
    )


@router.post("/plans/{plan_id}/change")
async def change_plan(
    plan_id: str, payload: PersonalMutation, request: Request, response: Response
):
    if "respond-async" in {value.strip() for value in request.headers.get("Prefer", "").lower().split(",")}:
        settings, plans, owner = context(request, response)
        try:
            saved = plans.get_owned(plan_id, owner_actor_hash=owner)
        except (PlanNotFoundError, PlanOwnerMismatchError, PlanReadOnlyError) as exc:
            raise HTTPException(404, "Planen finns inte i din session.") from exc
        from app.services.plan_jobs import PlanJobsFull
        key = hashlib.sha256(json.dumps([plan_id, payload.model_dump(mode="json"),
            _planner_admission_key(saved.request, settings)], sort_keys=True).encode()).hexdigest()
        try:
            job = _plan_jobs(request, settings).start(owner, key, request.state.request_id,
                lambda: _change_plan(plan_id, payload, request, response))
        except PlanJobsFull as exc:
            raise HTTPException(503, "Det är många som skapar menyer just nu.", headers={"Retry-After": "10"}) from exc
        return _pending_plan_job(job)
    return await _change_plan(plan_id, payload, request, response)


async def _change_plan(plan_id, payload, request, response):
    settings, plans, owner = context(request, response)
    private = PersonalStore(plans)
    try:
        saved = plans.get_owned(plan_id, owner_actor_hash=owner)
    except (PlanNotFoundError, PlanOwnerMismatchError, PlanReadOnlyError) as exc:
        raise HTTPException(404, "Planen finns inte i din session.") from exc
    if saved.plan.personal is None:
        raise HTTPException(422, "Öppna den äldre planen i dess befintliga redigeringsflöde.")
    state = private.read(owner)
    mutation_key = hashlib.sha256(
        json.dumps([plan_id, payload.model_dump(mode="json")], sort_keys=True).encode()
    ).hexdigest()
    prior = state.get("mutations", {}).get(mutation_key)
    if prior:
        return {
            "saved": plans.get_owned(plan_id, owner_actor_hash=owner, revision=prior),
            "state": public_state(state, request),
        }
    if payload.action in {"purchase", "consume", "release"}:
        try:
            target = plans.get_owned(plan_id, owner_actor_hash=owner, revision=payload.revision)
        except PlanNotFoundError as exc:
            raise PersonalConflict("Planrevisionen finns inte. Läs om planen.") from exc
        state = private.inventory_action(
            owner,
            target,
            payload.action,
            payload.pantry_revision,
            operation_id=payload.operation_id,
            consume_fraction=payload.consume_fraction,
            measured_purchase_quantities=payload.measured_purchase_quantities,
        )
        return {"saved": saved, "state": public_state(state, request)}
    if saved.revision != payload.revision:
        raise PersonalConflict("Planen ändrades. Senaste fungerande resultat är bevarat.")
    if payload.pantry_revision != state["revision"]:
        raise PersonalConflict("Skafferiet ändrades. Läs om innan ändring.")
    state = private.prepare_revision(owner, saved)
    prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request(saved.request.postal_code, {})
    if prepared is None:
        raise HTTPException(503, "Lokalt prisunderlag saknas.")
    spec = saved.request.personal.model_copy(deep=True)
    spec.slots = [s.model_copy(deep=True) for s in saved.plan.personal.slots]
    spec.pantry_revision = state["revision"]
    replace_slot = None
    if payload.action in {"edit", "replace", "remove"}:
        slot = next((s for s in spec.slots if s.id == payload.slot_id), None)
        if slot is None:
            raise HTTPException(422, "Måltidstillfället saknas.")
        if payload.action == "edit":
            if payload.recipe is None:
                raise HTTPException(422, "Ett strukturerat recept krävs.")
            slot.recipe = payload.recipe
        elif payload.action == "remove":
            slot.recipe = None
        else:
            if payload.recipe_id:
                from app.services.complete_recipes import enabled, identity
                from app.services.recipe_library import meal_candidates
                if not enabled(saved.request):
                    raise HTTPException(422, "Recept-ID kräver genomarbetat receptläge.")
                meal = next(m for m in spec.meals if m.meal_type == slot.meal_type)
                selected = next((r for r in meal_candidates(meal,saved.request.recipe_preferences)
                                 if identity(r) == payload.recipe_id), None)
                if selected is None:
                    raise HTTPException(422, "Receptet uppfyller inte dina val. Välj ett annat alternativ.")
                slot.recipe = selected
            else:
                replace_slot = slot.id
    elif payload.action == "restore_revision":
        if payload.restore_revision is None:
            raise HTTPException(422, "Välj en historisk planrevision.")
        try:
            historic = plans.get_owned(
                plan_id, owner_actor_hash=owner, revision=payload.restore_revision
            )
        except PlanNotFoundError as exc:
            raise PersonalConflict("Den historiska revisionen finns inte.") from exc
        if historic.plan.personal is None:
            raise HTTPException(422, "Revisionen saknar personligt planunderlag.")
        # Restore recipe content only; current confirmed policies/extras remain binding.
        spec.slots = [s.model_copy(deep=True) for s in historic.plan.personal.slots]
    elif payload.action == "product":
        if not payload.product_key or not payload.ingredient:
            raise HTTPException(422, "Välj en identifierad produkt och inköpsrad.")
        if payload.ingredient not in {n["key"] for n in saved.plan.personal.needs}:
            raise HTTPException(422, "Inköpsraden finns inte i planen.")
        spec.product_locks[payload.ingredient] = payload.product_key
    elif payload.action == "extras":
        if payload.extras is None:
            raise HTTPException(422, "Extravaror saknas.")
        spec.extras = payload.extras
    elif payload.action == "add_recipe":
        from uuid import uuid4

        from app.models.personal import MealSettings, MealSlot

        if payload.recipe is None:
            raise HTTPException(422, "Välj ett recept till det nya tillfället.")
        meal = next((m for m in spec.meals if m.meal_type == "dinner"), None)
        if meal is None:
            meal = MealSettings(count=0, servings=payload.recipe.servings)
            spec.meals.append(meal)
        if meal.count >= 7:
            raise HTTPException(
                422, "Planen har redan sju middagstillfällen. Byt ett befintligt recept."
            )
        meal.count += 1
        spec.slots.append(
            MealSlot(id=uuid4().hex, day=meal.count, meal_type="dinner", recipe=payload.recipe)
        )
    try:
        spec = PersonalPlanning.model_validate(spec.model_dump())
    except ValidationError as exc:
        raise HTTPException(
            422, "Ändringen strider mot antalet tillfällen eller vald fördelning."
        ) from exc
    plan_request = saved.request.model_copy(update={"personal": spec})
    plan = _with_release(
        await _run_personal_work(
            plan_request,
            request,
            settings,
            state["revision"],
            lambda: _run_personal_thread(
                lambda: PersonalPlanner(
                    plan_request, settings, prepared, state, plan_id=plan_id
                ).create(replace_slot=replace_slot)
            ),
            operation=f"{plan_id}:{saved.revision}:{payload.action}:{replace_slot}",
        ),
        settings,
    )
    saved = plans.append(
        plan_id=plan_id,
        request=plan_request,
        response=plan,
        operation="product_replaced" if payload.action == "product" else "recipe_replaced",
        expected_parent=payload.revision,
        owner_actor_hash=owner,
        mutation_key=mutation_key,
    )
    return {"saved": saved, "state": public_state(private.read(owner), request)}


@router.get("/plans/{plan_id}/surplus-suggestions")
async def surplus_suggestions(plan_id: str, request: Request, response: Response):
    settings, plans, owner = context(request, response)
    try:
        saved = plans.get_owned(plan_id, owner_actor_hash=owner)
    except (PlanNotFoundError, PlanOwnerMismatchError, PlanReadOnlyError) as exc:
        raise HTTPException(404, "Planen finns inte i din session.") from exc
    if not saved.plan.personal:
        raise HTTPException(422, "Planen saknar personligt skafferiunderlag.")
    state = PersonalStore(plans).read(owner)
    spec = saved.request.personal.model_copy(update={"pantry_revision": state["revision"]})
    prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request(saved.request.postal_code, {})
    if prepared is None:
        raise HTTPException(503, "Lokalt prisunderlag saknas.")
    plan_request = saved.request.model_copy(update={"personal": spec})
    return {
        "suggestions": await _run_personal_work(
            plan_request,
            request,
            settings,
            state["revision"],
            lambda: _run_personal_thread(
                lambda: PersonalPlanner(
                    plan_request, settings, prepared, state, plan_id=plan_id
                ).surplus_suggestions(saved.plan)
            ),
            operation=f"suggestions:{plan_id}:{saved.revision}",
        )
    }


def install_handlers(app):
    from app.services.basket_calculator import GroupPricingError
    from fastapi.responses import JSONResponse

    @app.exception_handler(GroupPricingError)
    async def blocked_group(_request, _exc):
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Kampanjgruppens underlag eller kombination kan inte verifieras. Senaste fungerande plan är bevarad. Välj andra varor eller gå tillbaka.",
                "code": "DATA_BLOCKED",
            },
            headers={"Cache-Control": "private, no-store"},
        )

    @app.exception_handler(PersonalConflict)
    async def stale_personal(_request, exc):
        return JSONResponse(
            status_code=409,
            content={"detail": str(exc), "code": "REVISION_CONFLICT"},
            headers={"Cache-Control": "private, no-store"},
        )

    @app.exception_handler(PolicyConflict)
    async def blocked_personal(_request, exc):
        return JSONResponse(
            status_code=422,
            content={
                "detail": str(exc),
                "code": exc.code,
                "conflicts": exc.conflicts,
                "planning_diagnostics": exc.diagnostics,
            },
            headers={"Cache-Control": "private, no-store"},
        )
