from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from app.config import Settings, get_settings
from app.errors import IncompleteBasketError, PriceProviderError
from app.models import (
    PlanProductEvidenceRequest,
    PlanRequest,
    PlanResponse,
    ProductAlternative,
    ProductLookupResponse,
    ReplaceProductRequest,
    ReplaceRecipeRequest,
    SavedPlan,
)
from app.services.beta_observability import pseudonymous_actor
from app.services.meal_plan_optimizer import MealPlanService
from app.services.personal_policy import PolicyConflict
from app.services.personal_store import PersonalConflict
from app.services.plan_jobs import PlanJobs, PlanJobsFull
from app.services.plan_mutation import (
    product_alternatives,
    replace_product,
    replace_recipe,
)
from app.services.plan_store import (
    PlanNotFoundError,
    PlanOwnerMismatchError,
    PlanReadOnlyError,
    PlanStore,
)
from app.services.planner_admission import (
    PlannerAdmissionController,
    PlannerAdmissionOverloaded,
)
from app.services.price_universe_runtime import (
    GLOBAL_PREPARED_PRICE_UNIVERSES,
    normalized_memberships,
)
from app.services.product_lookup import lookup_gtin
from app.services.user_pricing import current_pricing_date
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from grocery_data.app.api.community_evidence import (
    CommunityEvidenceResponse,
    get_community_session,
    persist_community_evidence,
)
from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.domain.community_evidence import CommunityEvidenceSubmission
from grocery_data.app.domain.identifiers import InvalidGtinError

router = APIRouter(prefix="/api", tags=["meal plan"])


def _service(request: PlanRequest | None = None) -> MealPlanService:
    settings = get_settings()
    if request is not None:
        settings = replace(
            settings,
            allow_estimated_quantities=request.purchase_planning_mode == "estimated",
        )
    return MealPlanService(
        settings,
        price_universe_manager=GLOBAL_PREPARED_PRICE_UNIVERSES,
    )


def _store(http_request: Request | None = None) -> PlanStore:
    """Reuse the process-lifetime store when it matches active configuration.

    The fallback keeps direct/unit-test use deterministic, while normal ASGI
    requests avoid rerunning SQLite schema discovery and DDL on every route.
    """

    settings = get_settings()
    if http_request is not None:
        configured = getattr(http_request.app.state, "plan_store", None)
        if (
            isinstance(configured, PlanStore)
            and configured.path == settings.plan_store_path.expanduser().resolve()
        ):
            return configured
    return PlanStore(settings.plan_store_path)


def _plan_actor_hash(http_request: Request, settings: Settings) -> str:
    """Return only the keyed capability derived by the request middleware."""

    from app.api.account import verified_owner

    account = verified_owner(http_request)
    if account:
        return account
    owner_actor_hash = pseudonymous_actor(
        getattr(http_request.state, "anonymous_session_id", None),
        settings,
    )
    if owner_actor_hash is None:
        raise HTTPException(
            status_code=503,
            detail="Planens anonyma ägarsession kunde inte upprättas.",
            headers={"X-Error-Code": "saved_plan_owner_session_unavailable"},
        )
    return owner_actor_hash


def _plan_write_forbidden(
    error: PlanReadOnlyError | PlanOwnerMismatchError,
) -> HTTPException:
    if isinstance(error, PlanReadOnlyError):
        return HTTPException(
            status_code=403,
            detail="Den här äldre sparade planen är skrivskyddad och kan inte ändras.",
            headers={"X-Error-Code": "saved_plan_read_only"},
        )
    return HTTPException(
        status_code=403,
        detail=("Planen kan bara ändras från den anonyma webbläsarsession som skapade den."),
        headers={"X-Error-Code": "saved_plan_owner_required"},
    )


def _plan_read_forbidden(
    error: PlanReadOnlyError | PlanOwnerMismatchError,
) -> HTTPException:
    if isinstance(error, PlanReadOnlyError):
        return HTTPException(
            status_code=403,
            detail=(
                "Den här äldre sparade planen saknar en säker ägarsession och "
                "kan därför inte öppnas."
            ),
            headers={"X-Error-Code": "saved_plan_owner_unavailable"},
        )
    return HTTPException(
        status_code=403,
        detail=("Planen kan bara öppnas från den anonyma webbläsarsession som skapade den."),
        headers={"X-Error-Code": "saved_plan_owner_required"},
    )


def _planner_admission(
    http_request: Request,
    settings: Settings,
) -> PlannerAdmissionController:
    """Return the process-lifetime admission controller for this ASGI app."""

    configured = getattr(http_request.app.state, "planner_admission", None)
    if isinstance(configured, PlannerAdmissionController):
        return configured
    # Direct TestClient/router use does not always execute the application
    # lifespan. Attach one controller to app state before the first await so
    # all requests on that app still share the same admission boundary.
    configured = PlannerAdmissionController(
        max_concurrent=settings.planner_max_concurrent_requests,
        max_queued=settings.planner_max_queued_requests,
    )
    http_request.app.state.planner_admission = configured
    return configured


def _planner_admission_key(request: PlanRequest, settings: Settings) -> str:
    """Hash the full economic request and active immutable universe identity."""

    memberships = normalized_memberships(
        request.pricing_memberships or None,
        use_member_prices=request.use_member_prices,
    )
    prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request(
        request.postal_code,
        memberships,
    )
    freshness_identity_resolver = getattr(
        prepared,
        "request_freshness_identity",
        None,
    )
    freshness_identity = (
        freshness_identity_resolver(
            stale_age_hours=settings.max_price_age_hours,
        )
        if callable(freshness_identity_resolver)
        else None
    )
    payload = {
        "request": request.model_dump(mode="json"),
        "price_universe_id": (prepared.universe.universe_id if prepared is not None else None),
        "price_context_freshness_identity": freshness_identity,
        "pricing_date": current_pricing_date().isoformat(),
        # These process settings can change deterministic search semantics but
        # are intentionally secret-free.
        "planner": {
            "price_provider": settings.price_provider,
            "meal_plan_strategy": settings.meal_plan_strategy,
            "stable_candidate_search_enabled": (settings.stable_candidate_search_enabled),
            "stable_candidate_base_count": settings.stable_candidate_base_count,
            "stable_candidate_search_limit": settings.stable_candidate_search_limit,
            "allow_medium_semantic_matches": settings.allow_medium_semantic_matches,
            "allow_estimated_quantities": settings.allow_estimated_quantities,
            "allow_unknown_quantities": settings.allow_unknown_quantities,
            "allow_unknown_sale_model": settings.allow_unknown_sale_model,
        },
    }
    from app.services.planner_context import fact_source_contract, settings_contract
    payload["planner_contract"] = settings_contract(settings)
    payload["fact_sources"] = fact_source_contract()
    if request.recipe_preferences is not None:
        from app.services.recipe_library import library_version
        payload["recipe_library"] = library_version()
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def _run_admitted_plan(
    request: PlanRequest,
    http_request: Request,
    settings: Settings,
) -> PlanResponse:
    if request.personal is not None:
        from app.services.personal_planner import PersonalPlanner
        from app.services.personal_store import PersonalStore
        from app.services.planner_artifacts import OwnedPlannerArtifacts

        owner = _plan_actor_hash(http_request, settings)
        artifacts = (OwnedPlannerArtifacts(_store(http_request), owner)
                     if settings.library_search_policy == "smako-verified-reference-v1" else None)
        state = PersonalStore(_store(http_request)).read(owner)
        prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request(request.postal_code, {})
        if prepared is None:
            raise HTTPException(503, "Lokalt prisunderlag saknas.")
        # Isolate admission/coalescing even when two owners choose equal fields.
        # Catalog/fact initialization belongs inside the admitted worker too:
        # it must neither block the event loop nor precede a long queue wait.
        return await _run_personal_work(
            request,
            http_request,
            settings,
            state["revision"],
            lambda: _run_personal_thread(
                lambda: PersonalPlanner(request, settings, prepared, state,
                    artifacts=artifacts).create()
            ),
        )
    controller = _planner_admission(http_request, settings)
    key = _planner_admission_key(request, settings)
    try:
        return await controller.run(
            key,
            lambda: _service(request).create_plan(request),
        )
    except PlannerAdmissionOverloaded as exc:
        raise HTTPException(
            status_code=503,
            detail=("Det är många som skapar menyer just nu. Försök igen om några sekunder."),
            headers={
                "Retry-After": "10",
                "X-Error-Code": "planner_admission_full",
            },
        ) from exc


async def _run_personal_thread(work):
    """Request cooperative stop, retaining admission until the worker exits.

    Cancelling asyncio.to_thread only abandons its await, not the running
    calculation. Shield and join it before propagating cancellation so a
    disconnect/shutdown cannot admit uncontrolled overlapping workers.
    """
    from app.services.plan_jobs import cancellable_work

    with cancellable_work() as stop:
        worker = asyncio.create_task(asyncio.to_thread(work))
        cancelled = None
        while not worker.done():
            try:
                await asyncio.shield(worker)
            except asyncio.CancelledError as exc:
                stop.set()
                cancelled = exc
            except Exception:
                if cancelled is not None:
                    raise cancelled
                raise
        if cancelled is not None:
            if not worker.cancelled():
                worker.exception()  # Consume any error before discarding the result.
            raise cancelled
        return worker.result()


async def _run_personal_work(
    request, http_request, settings, revision, work, *, operation="create"
):
    key = _planner_admission_key(request, settings)
    owner = _plan_actor_hash(http_request, settings)
    key = hashlib.sha256(f"{key}:{owner}:{revision}:{operation}".encode()).hexdigest()
    try:
        return await _planner_admission(http_request, settings).run(key, work)
    except PlannerAdmissionOverloaded as exc:
        raise HTTPException(
            503,
            "Det är många som beräknar korgar. Försök igen om några sekunder.",
            headers={"Retry-After": "10"},
        ) from exc


def _with_release(plan: PlanResponse, settings: Settings) -> PlanResponse:
    """Bind the serving release to the reproducible consumer result."""

    return plan.model_copy(
        update={"app_version": settings.app_version, "build_id": settings.build_id}
    )


def _form_error(field: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail=[{"loc": ["body", field], "msg": message, "type": "value_error"}],
        headers={"X-Error-Code": "form_validation_error"},
    )


def _consumer_request(request: PlanRequest) -> PlanRequest:
    if request.personal is not None:
        if request.max_stores > 3:
            raise _form_error("max_stores", "Välj 1, 2 eller 3 inköpsställen")
        if request.strategy == "legacy":
            raise HTTPException(422, "Personlig planering använder den gemensamma optimeraren.")
        if request.diet_preference.value not in {"mixed", "meat_allowed"} and any(
            m.diet != request.diet_preference.value for m in request.personal.meals
        ):
            raise HTTPException(422, "Måltidernas kostval strider mot planens kostval.")
        return request.model_copy(update={"strategy": "optimized", "debug": False})
    if request.recipes < 3:
        raise _form_error("recipes", "Välj 3–7 middagar")
    if request.servings > 8:
        raise _form_error("servings", "Välj 1–8 portioner")
    if request.max_stores > 3:
        raise _form_error("max_stores", "Välj 1, 2 eller 3 inköpsställen")
    if request.strategy == "legacy":
        raise HTTPException(status_code=422, detail="consumer plans require optimized strategy")
    return request.model_copy(update={"strategy": "optimized", "debug": False})


def _production_consumer_request(
    request: PlanRequest,
    settings: Settings,
) -> PlanRequest:
    """Reject public requests that can expand planner work beyond the beta budget."""

    request = request.model_copy(update={"membership_price_policy": "all_advertised"})
    if settings.app_env != "production":
        return request
    if request.personal is not None:
        return _consumer_request(request)
    # Apply form limits before the separate computational-budget guard, so a
    # genuine input error identifies the field rather than a server/model field.
    _consumer_request(request)
    exceeds_budget = (
        request.recipes < 3
        or request.servings > 8
        or request.max_stores > 3
        or request.strategy == "legacy"
        or request.optimization_iterations > 1
        or request.candidate_recipe_count > 80
        or (request.candidate_search_limit is not None and request.candidate_search_limit > 160)
        or request.beam_width > 30
        or request.debug
    )
    if exceeds_budget:
        raise HTTPException(
            status_code=422,
            detail="Begäran ligger utanför betans tillåtna planeringsgränser.",
            headers={"X-Error-Code": "consumer_request_budget_exceeded"},
        )
    return _consumer_request(request)


def _assert_offline_plan(plan: PlanResponse) -> None:
    if plan.data is not None and plan.data.live_chain_requests != 0:
        raise HTTPException(
            status_code=503,
            detail="consumer planning attempted a live source request",
            headers={"X-Error-Code": "planner_offline_violation"},
        )
    # A prepared artifact preserves the source name that built it (for example
    # "federated" or "own").  Presence of immutable PlanPriceData plus the
    # preflight above is the offline proof; source labels must not be rewritten.
    if plan.data is None and plan.data_source != "mock":
        raise HTTPException(
            status_code=503,
            detail="consumer planning requires an active local PriceUniverse",
            headers={"X-Error-Code": "planner_offline_violation"},
        )


def _assert_offline_ready(request: PlanRequest, settings: Settings) -> None:
    """Fail before service execution when a local immutable universe is absent."""

    if settings.price_provider == "mock":
        return
    memberships = normalized_memberships(
        request.pricing_memberships or None,
        use_member_prices=request.use_member_prices,
    )
    prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request(
        request.postal_code,
        memberships,
    )
    if prepared is None:
        city = " ".join(settings.price_universe_city.casefold().split())
        active = GLOBAL_PREPARED_PRICE_UNIVERSES.get_active(f"city:{city}")
        if active is not None and request.postal_code not in active.universe.key.postal_codes:
            supported = ", ".join(sorted(active.universe.key.postal_codes))
            raise _form_error(
                "postal_code",
                "Det finns inget aktiverat prisområde för postnumret. "
                f"Tillgängliga postnummer i betan: {supported}",
            )
        raise HTTPException(
            status_code=503,
            detail="consumer planning requires a matching active local PriceUniverse",
            headers={"X-Error-Code": "price_universe_unavailable"},
        )
    status = prepared.status(
        warning_age_hours=settings.price_age_warning_hours,
        stale_age_hours=settings.max_price_age_hours,
    )
    usable, _stale, _ages = prepared._context_partition(
        now=datetime.now(UTC), stale_age_hours=settings.max_price_age_hours
    )
    from app.services.municipal_runtime import required_contexts
    if status.status in {"stale", "broken"} or (required_contexts(settings, prepared) - set(usable)):
        raise HTTPException(
            status_code=503,
            detail="active local PriceUniverse is not usable for consumer planning",
            headers={"X-Error-Code": "price_universe_unusable"},
        )


def _annotate_freshness(saved: SavedPlan) -> SavedPlan:
    # Saved consumer-plan reads are always the normal public projection. This
    # also protects plans persisted by versions that included raw diagnostics.
    saved = saved.model_copy(
        update={
            "plan": saved.plan.model_copy(
                update={"source_diagnostics": [], "debug_info": None},
                deep=True,
            )
        }
    )
    if saved.price_universe_id is None:
        return saved
    prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request(
        saved.request.postal_code,
        normalized_memberships(
            saved.request.pricing_memberships or None,
            use_member_prices=saved.request.use_member_prices,
        ),
    )
    if prepared is None:
        return saved.model_copy(
            update={
                "price_version_status": "unavailable",
                "active_price_freshness": None,
                "recalculation_available": False,
            }
        )
    active_id = prepared.universe.universe_id
    settings = get_settings()
    active_status = prepared.status(
        warning_age_hours=settings.price_age_warning_hours,
        stale_age_hours=settings.max_price_age_hours,
    ).status
    changed = active_id != saved.price_universe_id
    unavailable_saved_context_ids: tuple[str, ...] = ()
    request_view = getattr(prepared, "request_view", None)
    if not changed and callable(request_view):
        current_view = request_view(stale_age_hours=settings.max_price_age_hours)
        current_context_ids = frozenset(current_view.usable_context_ids)
        saved_context_ids = {group.store_id for group in saved.plan.optimized_basket.stores}
        unavailable_saved_context_ids = tuple(sorted(saved_context_ids - current_context_ids))
    coverage_changed = bool(unavailable_saved_context_ids)
    if changed:
        price_version_status = "newer_available"
    elif coverage_changed:
        price_version_status = "coverage_changed"
    else:
        price_version_status = "current"
    return saved.model_copy(
        update={
            "prices_changed_since_creation": changed,
            "price_contexts_changed_since_creation": coverage_changed,
            "unavailable_saved_context_ids": unavailable_saved_context_ids,
            "price_version_status": price_version_status,
            "active_price_freshness": active_status,
            "recalculation_available": (changed or coverage_changed)
            and active_status not in {"stale", "broken"},
        }
    )


def _package_description(item: object) -> str | None:
    quantity = getattr(item, "package_quantity", None)
    unit = getattr(item, "package_unit", None)
    if quantity is None or unit is None:
        return None
    rendered = f"{quantity:g}" if float(quantity).is_integer() else str(quantity)
    return f"{rendered} {unit}"


def _plan_product_submission(
    saved: SavedPlan,
    product_id: str,
    payload: PlanProductEvidenceRequest,
) -> CommunityEvidenceSubmission:
    matches = [
        (group, item)
        for group in saved.plan.optimized_basket.stores
        for item in group.items
        if item.product_id == product_id
    ]
    if not matches:
        raise HTTPException(status_code=404, detail="product not found in saved plan")
    identities = {(item.store_id, item.product_id) for _group, item in matches}
    if len(identities) != 1:
        raise HTTPException(
            status_code=409,
            detail="product occurs in multiple price contexts; select an exact basket row",
        )
    group, item = matches[0]
    provenance = item.source_provenance
    price_snapshot_id = (
        provenance.source_snapshot_id if provenance is not None else saved.price_universe_id
    )
    try:
        return CommunityEvidenceSubmission(
            evidence_type=payload.evidence_type,
            evidence_source=payload.evidence_source,
            anonymous_session_id=payload.anonymous_session_id,
            user_id=payload.user_id,
            observed_at=payload.observed_at,
            chain=item.chain,
            physical_store_id=payload.physical_store_id,
            store_display_name=group.store_name,
            grocery_context_id=item.store_id,
            gtin=item.gtin,
            source_product_id=item.product_id,
            product_name=item.product_name,
            package_description=_package_description(item),
            shelf_price=payload.shelf_price,
            digital_price=Decimal(str(item.unit_price)),
            unit_price=payload.unit_price,
            price_unit=payload.price_unit,
            quantity=payload.quantity,
            promotion=payload.promotion,
            plan_id=saved.plan_id,
            price_snapshot_id=price_snapshot_id,
            note=payload.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _community_settings(request: Request) -> GroceryDataSettings:
    configured = getattr(request.app.state, "community_evidence_settings", None)
    if isinstance(configured, GroceryDataSettings):
        return configured
    return GroceryDataSettings.from_env()


@router.post("/plan", response_model=PlanResponse)
async def create_plan(
    request: PlanRequest,
    http_request: Request,
    debug: bool | None = None,
) -> PlanResponse:
    """Create a price-driven menu and a package-aware optimized basket."""
    settings = get_settings()
    return await _with_current_deadline(settings, lambda: _create_plan_body(request, http_request, settings, debug))


async def _create_plan_body(request: PlanRequest, http_request: Request, settings: Settings, debug=None):
    if debug is not None:
        request = request.model_copy(update={"debug": debug})
    request = _production_consumer_request(request, settings)
    request = _prepare_complete_request(request, http_request, settings)
    if settings.price_universe_required:
        _assert_offline_ready(request, settings)
    try:
        plan = _with_release(
            await _with_current_deadline(settings, lambda: _run_admitted_plan(request, http_request, settings)),
            settings,
        )
        if settings.price_universe_required:
            _assert_offline_plan(plan)
        return plan
    except (PolicyConflict, PersonalConflict):
        raise
    except IncompleteBasketError as exc:
        raise HTTPException(status_code=422, detail=str(exc),
                            headers={"X-Error-Code": "plan_infeasible"}) from exc
    except PriceProviderError as exc:
        raise HTTPException(status_code=502, detail="price provider unavailable") from exc
    except ValueError as exc:
        # Request validation has already completed. A model/configuration error
        # inside planning is a server failure, never evidence of a bad form field.
        raise HTTPException(status_code=500, detail="Planeringstjänsten kunde inte slutföra menyn.",
                            headers={"X-Error-Code": "planner_internal_error"}) from exc


@router.post("/plans", response_model=SavedPlan, status_code=201)
async def create_saved_plan(request: PlanRequest, http_request: Request):
    """Create and persist a reproducible, provider-offline consumer plan."""
    settings = get_settings()
    return await _with_current_deadline(settings, lambda: _prepare_saved_plan(request, http_request, settings))


async def _prepare_saved_plan(request: PlanRequest, http_request: Request, settings: Settings):
    request = _production_consumer_request(request, settings)
    request = _prepare_complete_request(request, http_request, settings)
    consumer_request = _consumer_request(request)
    _assert_offline_ready(consumer_request, settings)
    if "respond-async" in {value.strip() for value in http_request.headers.get("Prefer", "").lower().split(",")}:
        owner = _plan_actor_hash(http_request, settings)
        jobs = _plan_jobs(http_request, settings)
        try:
            job = jobs.start(
                owner, _job_request_key(consumer_request, http_request, settings),
                http_request.state.request_id,
                lambda: _create_saved_plan(consumer_request, http_request, settings),
            )
        except PlanJobsFull as exc:
            raise HTTPException(503, "Det är många som skapar menyer just nu.", headers={
                "X-Error-Code": "planner_admission_full", "Retry-After": "10",
            }) from exc
        return _pending_plan_job(job)
    return await _create_saved_plan(consumer_request, http_request, settings)


def _prepare_complete_request(request, http_request, settings):
    from app.services.membership import require_membership_limits
    require_membership_limits(request, http_request)
    from app.services.complete_recipes import enabled, prepare_request
    if not enabled(request):
        return request
    from app.services.personal_store import PersonalStore
    state = PersonalStore(_store(http_request)).read(_plan_actor_hash(http_request, settings))
    prepared = prepare_request(request, settings, pantry_revision=state["revision"])
    # The public form may now describe several meal types. Bind its implicit
    # pantry revision exactly as the existing public dinner translation does.
    prepared.personal.pantry_revision = state["revision"]
    return prepared


def _job_request_key(request, http_request, settings):
    key = _planner_admission_key(request, settings)
    if request.personal is not None:
        from app.services.personal_store import PersonalStore
        state = PersonalStore(_store(http_request)).read(_plan_actor_hash(http_request, settings))
        # Owned pantry revision must also bind the transport cache, before
        # admission; an old explicit revision must not return a stale success.
        key = hashlib.sha256(f"{key}:pantry:{state['revision']}".encode()).hexdigest()
    return key


def _plan_jobs(http_request: Request, settings: Settings) -> PlanJobs:
    jobs = getattr(http_request.app.state, "plan_jobs", None)
    if not isinstance(jobs, PlanJobs):
        jobs = PlanJobs(max_pending=settings.planner_max_concurrent_requests + settings.planner_max_queued_requests)
        http_request.app.state.plan_jobs = jobs
    return jobs


def _pending_plan_job(job):
    stage, progress = job.status  # One atomic snapshot from the worker thread.
    return JSONResponse(status_code=202, content={
        "status": "pending", "status_url": f"/api/plan-jobs/{job.job_id}",
        "request_id": job.request_id,
        "stage": stage,
        "progress": progress,
    }, headers={"Cache-Control": "private, no-store", "Retry-After": "2",
                "Preference-Applied": "respond-async"})


@router.delete("/plan-jobs/{job_id}", status_code=202)
async def cancel_plan_job(job_id: str, http_request: Request):
    settings = get_settings()
    job = _plan_jobs(http_request, settings).get(job_id, _plan_actor_hash(http_request, settings))
    headers = {"Cache-Control": "private, no-store"}
    if job is None:
        raise HTTPException(404, "Planeringsförsöket finns inte i din session.", headers=headers)
    if job.task.done() and not job.task.cancelled():
        raise HTTPException(409, "Planeringsförsöket är redan avslutat.", headers=headers)
    if not job.task.done():
        job.status = ("cancelling", None)
        job.task.cancel()
    return JSONResponse(status_code=202, content={
        "status": "cancelled" if job.task.cancelled() else "cancelling",
        "status_url": f"/api/plan-jobs/{job.job_id}",
    }, headers=headers)


@router.get("/plan-jobs/{job_id}", response_model=SavedPlan, status_code=201)
async def poll_plan_job(job_id: str, http_request: Request):
    settings = get_settings()
    job = _plan_jobs(http_request, settings).get(job_id, _plan_actor_hash(http_request, settings))
    if job is None or job.task.cancelled():
        raise HTTPException(404, "Planeringsförsöket har gått ut. Skapa menyn igen.",
                            headers={"X-Error-Code": "planner_job_expired", "Cache-Control": "private, no-store"})
    # Only an authenticated owner lookup may attach job evidence to this read.
    http_request.state.diagnostic_plan_job = job
    if not job.task.done():
        return _pending_plan_job(job)
    # Never raise the task's retained exception object in a reader coroutine.
    # A completion callback releases its planner traceback frames; attaching
    # live request frames to that same object can clear a suspended reader.
    error = job.task.exception()
    if isinstance(error, (PolicyConflict, PersonalConflict)):
        from app.api.personal import personal_conflict_response
        response = personal_conflict_response(error)
        response.headers["X-Plan-Request-ID"] = job.request_id
        return response
    if isinstance(error, HTTPException):
        raise HTTPException(error.status_code, error.detail, headers={
            **(error.headers or {}), "Cache-Control": "private, no-store",
            "X-Plan-Request-ID": job.request_id,
        })
    if error is not None:
        raise RuntimeError("Planeringsjobbet avslutades med ett serverfel.") from error
    saved = job.task.result()
    from fastapi.encoders import jsonable_encoder
    content = jsonable_encoder(saved) if isinstance(saved, dict) else _annotate_freshness(saved).model_dump(mode="json")
    return JSONResponse(status_code=201, content=content,
                        headers={"Cache-Control": "private, no-store", "X-Plan-Request-ID": job.request_id})


@router.get("/plan-job-requests/{request_id}")
async def find_plan_job(request_id: str, http_request: Request):
    """Recover an accepted start whose response was lost; never start new work."""
    settings = get_settings()
    job = _plan_jobs(http_request, settings).by_request(request_id, _plan_actor_hash(http_request, settings))
    if job is None:
        raise HTTPException(404, "Startförsöket kan inte återfinnas i din session. Det kan ha gått ut eller avslutats vid serveromstart. Ingen ny beräkning har startats.",
                            headers={"X-Error-Code": "planner_job_expired", "Cache-Control": "private, no-store"})
    return _pending_plan_job(job)


async def _with_current_deadline(settings, work):
    if getattr(settings, "library_search_policy", "legacy") != "smako-current-library-v2":
        return await work()
    from app.services.plan_jobs import (
        PlanningDeadlineExceeded,
        check_cancelled,
        planning_deadline,
        remaining_planning_seconds,
    )
    try:
        with planning_deadline(60):
            # Includes awaited admission, not only cooperative CPU-loop checks.
            timer = asyncio.timeout(remaining_planning_seconds())
            try:
                async with timer:
                    result = await work()
            except TimeoutError as exc:
                if not timer.expired():
                    raise
                raise PlanningDeadlineExceeded("The complete planning deadline expired while awaiting work") from exc
            except PlanningDeadlineExceeded:
                raise
            except PolicyConflict:
                raise  # Preserve an inner deadline's committed-revision receipt.
            except Exception:
                check_cancelled()  # E.g. a storage lock wait exhausted the remaining budget.
                raise
            check_cancelled()  # Includes mandatory checkout and persistence.
            return result
    except PlanningDeadlineExceeded as exc:
        raise PolicyConflict(
            "Sökningen är ofullständig efter tidsgränsen. Ingen slutkontrollerad lista kunde levereras. Dina krav har inte ändrats.",
            code="SEARCH_INCOMPLETE", stage="search_deadline",
            diagnostics=getattr(exc, "diagnostics", None),
        ) from exc


async def _create_saved_plan(consumer_request: PlanRequest, http_request: Request, settings: Settings) -> SavedPlan:
    return await _with_current_deadline(settings, lambda: _create_saved_plan_body(consumer_request, http_request, settings))


async def _create_saved_plan_body(consumer_request: PlanRequest, http_request: Request, settings: Settings) -> SavedPlan:
    try:
        plan = _with_release(
            await _run_admitted_plan(consumer_request, http_request, settings),
            settings,
        )
        _assert_offline_plan(plan)
        from app.services.plan_jobs import report_stage
        report_stage("saving")
        return _annotate_freshness(
            _store(http_request).create(
                consumer_request,
                plan,
                owner_actor_hash=_plan_actor_hash(http_request, settings),
            )
        )
    except (PolicyConflict, PersonalConflict):
        raise
    except IncompleteBasketError as exc:
        raise HTTPException(status_code=422, detail=str(exc),
                            headers={"X-Error-Code": "plan_infeasible"}) from exc
    except PriceProviderError as exc:
        raise HTTPException(status_code=502, detail="price provider unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Planeringstjänsten kunde inte slutföra menyn.",
                            headers={"X-Error-Code": "planner_internal_error"}) from exc


@router.get("/plans/{plan_id}", response_model=SavedPlan)
async def get_saved_plan(
    plan_id: str,
    request: Request,
    revision: int | None = None,
) -> SavedPlan:
    settings = get_settings()
    try:
        return _annotate_freshness(
            _store(request).get_owned(
                plan_id,
                owner_actor_hash=_plan_actor_hash(request, settings),
                revision=revision,
            )
        )
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail="plan not found") from exc
    except (PlanReadOnlyError, PlanOwnerMismatchError) as exc:
        raise _plan_read_forbidden(exc) from exc


@router.get(
    "/plans/{plan_id}/products/{product_id}/alternatives",
    response_model=list[ProductAlternative],
)
async def get_product_alternatives(
    plan_id: str,
    product_id: str,
    request: Request,
) -> list[ProductAlternative]:
    settings = get_settings()
    try:
        saved = _store(request).get_owned(
            plan_id,
            owner_actor_hash=_plan_actor_hash(request, settings),
        )
        return product_alternatives(saved.plan, product_id)
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail="plan not found") from exc
    except (PlanReadOnlyError, PlanOwnerMismatchError) as exc:
        raise _plan_read_forbidden(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/plans/{plan_id}/replace-product", response_model=SavedPlan)
async def replace_saved_product(
    plan_id: str,
    request: ReplaceProductRequest,
    http_request: Request,
) -> SavedPlan:
    store = _store(http_request)
    settings = get_settings()
    owner_actor_hash = _plan_actor_hash(http_request, settings)
    try:
        saved = store.get_owned(plan_id, owner_actor_hash=owner_actor_hash)
        if saved.plan.personal is not None:
            raise ValueError(
                "Använd planens personliga redigeringsflöde för en gemensam omberäkning."
            )
        plan_request = saved.request.model_copy(update={"membership_price_policy": "all_advertised"})
        plan = replace_product(
            saved.plan,
            plan_request,
            product_id=request.product_id,
            replacement_product_id=request.replacement_product_id,
        )
        plan = _with_release(plan, settings)
        return _annotate_freshness(
            store.append(
                plan_id=plan_id,
                request=plan_request,
                response=plan,
                operation="product_replaced",
                expected_parent=saved.revision,
                owner_actor_hash=owner_actor_hash,
            )
        )
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail="plan not found") from exc
    except (PlanReadOnlyError, PlanOwnerMismatchError) as exc:
        raise _plan_write_forbidden(exc) from exc
    except (IncompleteBasketError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/plans/{plan_id}/replace-recipe", response_model=SavedPlan)
async def replace_saved_recipe(
    plan_id: str,
    request: ReplaceRecipeRequest,
    http_request: Request,
) -> SavedPlan:
    store = _store(http_request)
    settings = get_settings()
    owner_actor_hash = _plan_actor_hash(http_request, settings)
    try:
        saved = store.get_owned(plan_id, owner_actor_hash=owner_actor_hash)
        if saved.plan.personal is not None:
            raise ValueError(
                "Använd planens personliga redigeringsflöde för en gemensam omberäkning."
            )
        plan_request = saved.request.model_copy(update={"membership_price_policy": "all_advertised"})
        from app.services.membership import require_membership_limits
        require_membership_limits(plan_request, http_request)
        plan = await replace_recipe(
            saved.plan,
            plan_request,
            recipe_index=request.recipe_index,
            replacement_recipe_name=request.replacement_recipe_name,
            settings=settings,
        )
        plan = _with_release(plan, settings)
        return _annotate_freshness(
            store.append(
                plan_id=plan_id,
                request=plan_request,
                response=plan,
                operation="recipe_replaced",
                expected_parent=saved.revision,
                owner_actor_hash=owner_actor_hash,
            )
        )
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail="plan not found") from exc
    except (PlanReadOnlyError, PlanOwnerMismatchError) as exc:
        raise _plan_write_forbidden(exc) from exc
    except (IncompleteBasketError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/plans/{plan_id}/products/{product_id}/report",
    response_model=CommunityEvidenceResponse,
    status_code=201,
)
async def report_saved_plan_product(
    plan_id: str,
    product_id: str,
    payload: PlanProductEvidenceRequest,
    request: Request,
    session: Annotated[Session, Depends(get_community_session)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CommunityEvidenceResponse:
    """Append user evidence with identity and source facts bound by the server."""

    settings = get_settings()
    try:
        saved = _store(request).get_owned(
            plan_id,
            owner_actor_hash=_plan_actor_hash(request, settings),
        )
    except PlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail="plan not found") from exc
    except (PlanReadOnlyError, PlanOwnerMismatchError) as exc:
        raise _plan_read_forbidden(exc) from exc
    submission = _plan_product_submission(saved, product_id, payload)
    return persist_community_evidence(
        submission,
        session=session,
        settings=_community_settings(request),
        idempotency_key=idempotency_key,
    )


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/recipe-library")
async def recipe_library_metadata():
    from app.services.recipe_library import library_summary
    settings = get_settings()
    return {"enabled": settings.complete_recipes_enabled,
            "variation_intent_enabled":settings.library_search_policy == 'smako-current-library-v2', **library_summary()}


@router.get("/price-contexts")
async def available_price_contexts(postal_code: str = "22350",
    latitude: Annotated[float | None, Query(ge=-90, le=90)] = None,
    longitude: Annotated[float | None, Query(ge=-180, le=180)] = None):
    if (latitude is None) != (longitude is None):
        raise HTTPException(422, "Ange både latitud och longitud.")
    normalized = PlanRequest(postal_code=postal_code).postal_code
    prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request(normalized, {})
    if prepared is None:
        raise HTTPException(503, "Lokalt prisunderlag saknas.")
    settings = get_settings()
    view = prepared.request_view(stale_age_hours=settings.max_price_age_hours)
    from app.services.meal_plan_optimizer import _consumer_price_context_coverage
    compared, excluded = _consumer_price_context_coverage(prepared,
        usable_context_ids={s.store_id for s in view.stores},
        excluded_stale_context_ids=view.excluded_stale_context_ids)
    from app.services.municipal_runtime import distance_to_store
    stores = {store.store_id: store for store in view.stores}
    contexts = []
    for row in compared:
        value = row.model_dump(mode="json")
        store = stores.get(row.context_id)
        distance, basis = distance_to_store(store, latitude, longitude) if store else (None, None)
        value.update(distance_km=distance, distance_basis=basis,
                     address=store.address if store else None, city=store.city if store else None)
        contexts.append(value)
    if latitude is not None:
        contexts.sort(key=lambda row: (row["distance_km"] is None, row["distance_km"] or 0, row["display_name"]))
    return {"contexts": contexts,
            "excluded": [row.model_dump(mode="json") for row in excluded]}


@router.get("/municipalities")
async def available_municipalities():
    from app.services.municipal_runtime import configured_areas, required_contexts
    settings = get_settings()
    rows = []
    for scope in configured_areas(settings):
        prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_active("city:" + scope["city"].casefold())
        status, postal, available = "pending", scope.get("postal_code"), False
        if prepared is not None:
            postal = min(prepared.universe.key.postal_codes)
            usable, _stale, _ages = prepared._context_partition(now=datetime.now(UTC), stale_age_hours=settings.max_price_age_hours)
            status = prepared.status(stale_age_hours=settings.max_price_age_hours).status
            available = status not in {"stale", "broken"} and not (required_contexts(settings, prepared) - set(usable))
        rows.append({"municipality_code": scope["municipality_code"], "name": scope["city"],
                     "postal_code": postal, "available": available, "status": status})
    return {"municipalities": rows}


@router.get("/shopping-location")
async def shopping_location(postal_code: Annotated[str, Query(min_length=5, max_length=12)]):
    """Resolve real postcodes before selecting an existing prepared price area.

    No provider calls, no new collection scope, and no guessed store positions.
    Online fulfillment warehouses never count as nearby shops.
    """
    from app.services.municipal_runtime import distance_to_store
    from app.services.postal_locations import lookup_postcode
    try:
        location = lookup_postcode(postal_code)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if location["status"] != "located":
        return location
    areas = (await available_municipalities())["municipalities"]
    distances = []
    for area in areas:
        prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_active("city:" + area["name"].casefold())
        if prepared is None:
            continue
        for store in prepared.stores:
            distance, _basis = distance_to_store(store, location["latitude"], location["longitude"], precision=None)
            if distance is not None:
                distances.append((distance, area))
    if not distances:
        return {**location, "status": "unavailable", "nearest_distance_km": None}
    nearest, nearest_area = min(distances, key=lambda item: item[0])
    if nearest > 10:
        return {**location, "status": "outside_coverage", "nearest_distance_km": nearest}
    own_area = next((area for area in areas if area["municipality_code"] == location["municipality_code"]), None)
    area = own_area or nearest_area
    if not area["available"]:
        return {**location, "status": "unavailable", "nearest_distance_km": nearest}
    data = await available_price_contexts(area["postal_code"], location["latitude"], location["longitude"])
    # Keep full precision for radius eligibility; presentation may round later.
    prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request(area["postal_code"], {})
    stores = {store.store_id: store for store in prepared.stores} if prepared else {}
    for row in data["contexts"]:
        store = stores.get(row["context_id"])
        if store:
            row["distance_km"], row["distance_basis"] = distance_to_store(
                store, location["latitude"], location["longitude"], precision=None)
    return {**location, "status": "eligible", "nearest_distance_km": nearest,
            "area_postal_code": area["postal_code"], "area_name": area["name"],
            "municipality_available": own_area is not None, **data}


@router.get("/price-universe/status")
async def price_universe_status(city: str = "Lund") -> dict[str, object]:
    """Expose active immutable price metadata without triggering a rebuild."""

    normalized = " ".join(city.casefold().split())
    if not normalized:
        raise HTTPException(status_code=422, detail="city must not be blank")
    return GLOBAL_PREPARED_PRICE_UNIVERSES.status(f"city:{normalized}")


@router.get("/products/{gtin}", response_model=ProductLookupResponse)
async def get_product_by_gtin(gtin: str, city: str = "Lund") -> ProductLookupResponse:
    """Resolve an exact barcode locally; never search a live provider."""

    normalized_city = " ".join(city.casefold().split())
    if not normalized_city:
        raise HTTPException(status_code=422, detail="city must not be blank")
    prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_active(f"city:{normalized_city}")
    if prepared is None:
        raise HTTPException(status_code=503, detail="active PriceUniverse is unavailable")
    settings = get_settings()
    freshness_status = prepared.status(
        warning_age_hours=settings.price_age_warning_hours,
        stale_age_hours=settings.max_price_age_hours,
    )
    if freshness_status.status == "stale":
        raise HTTPException(
            status_code=503,
            detail="active PriceUniverse is not usable for product lookup",
        )
    freshness_view = prepared.request_view(
        stale_age_hours=settings.max_price_age_hours,
    )
    try:
        return lookup_gtin(
            prepared,
            gtin,
            allowed_context_ids=freshness_view.usable_context_ids,
        )
    except InvalidGtinError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/metrics/plans")
async def plan_metrics(request: Request) -> dict[str, object]:
    """Return privacy-safe aggregate planner dimensions only."""

    return {"dimensions": _store(request).aggregate_metrics()}
