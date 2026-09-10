from __future__ import annotations

import hashlib
import json
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
from fastapi import APIRouter, Depends, Header, HTTPException, Request
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


def _service() -> MealPlanService:
    return MealPlanService(
        get_settings(),
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
        detail=(
            "Planen kan bara ändras från den anonyma webbläsarsession som skapade den."
        ),
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
        detail=(
            "Planen kan bara öppnas från den anonyma webbläsarsession som skapade den."
        ),
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
        request.memberships or None,
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
        "price_universe_id": (
            prepared.universe.universe_id if prepared is not None else None
        ),
        "price_context_freshness_identity": freshness_identity,
        "pricing_date": current_pricing_date().isoformat(),
        # These process settings can change deterministic search semantics but
        # are intentionally secret-free.
        "planner": {
            "price_provider": settings.price_provider,
            "meal_plan_strategy": settings.meal_plan_strategy,
            "stable_candidate_search_enabled": (
                settings.stable_candidate_search_enabled
            ),
            "stable_candidate_base_count": settings.stable_candidate_base_count,
            "stable_candidate_search_limit": settings.stable_candidate_search_limit,
            "allow_medium_semantic_matches": settings.allow_medium_semantic_matches,
            "allow_estimated_quantities": settings.allow_estimated_quantities,
            "allow_unknown_quantities": settings.allow_unknown_quantities,
            "allow_unknown_sale_model": settings.allow_unknown_sale_model,
        },
    }
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
    controller = _planner_admission(http_request, settings)
    key = _planner_admission_key(request, settings)
    try:
        return await controller.run(
            key,
            lambda: _service().create_plan(request),
        )
    except PlannerAdmissionOverloaded as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Det är många som skapar menyer just nu. "
                "Försök igen om några sekunder."
            ),
            headers={
                "Retry-After": "10",
                "X-Error-Code": "planner_admission_full",
            },
        ) from exc


def _with_release(plan: PlanResponse, settings: Settings) -> PlanResponse:
    """Bind the serving release to the reproducible consumer result."""

    return plan.model_copy(
        update={"app_version": settings.app_version, "build_id": settings.build_id}
    )


def _consumer_request(request: PlanRequest) -> PlanRequest:
    if request.recipes < 3:
        raise HTTPException(status_code=422, detail="consumer plans require 3-7 meals")
    if request.servings > 8:
        raise HTTPException(status_code=422, detail="consumer plans support 1-8 servings")
    if request.max_stores > 3:
        raise HTTPException(status_code=422, detail="consumer plans support max 1-3 stores")
    if request.strategy == "legacy":
        raise HTTPException(status_code=422, detail="consumer plans require optimized strategy")
    return request.model_copy(update={"strategy": "optimized", "debug": False})


def _production_consumer_request(
    request: PlanRequest,
    settings: Settings,
) -> PlanRequest:
    """Reject public requests that can expand planner work beyond the beta budget."""

    if settings.app_env != "production":
        return request
    exceeds_budget = (
        request.recipes < 3
        or request.servings > 8
        or request.max_stores > 3
        or request.strategy == "legacy"
        or request.optimization_iterations > 1
        or request.candidate_recipe_count > 80
        or (
            request.candidate_search_limit is not None
            and request.candidate_search_limit > 160
        )
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
        )
    # A prepared artifact preserves the source name that built it (for example
    # "federated" or "own").  Presence of immutable PlanPriceData plus the
    # preflight above is the offline proof; source labels must not be rewritten.
    if plan.data is None and plan.data_source != "mock":
        raise HTTPException(
            status_code=503,
            detail="consumer planning requires an active local PriceUniverse",
        )


def _assert_offline_ready(request: PlanRequest, settings: Settings) -> None:
    """Fail before service execution when a local immutable universe is absent."""

    if settings.price_provider == "mock":
        return
    memberships = normalized_memberships(
        request.memberships or None,
        use_member_prices=request.use_member_prices,
    )
    prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request(
        request.postal_code,
        memberships,
    )
    if prepared is None:
        raise HTTPException(
            status_code=503,
            detail="consumer planning requires a matching active local PriceUniverse",
        )
    status = prepared.status(
        warning_age_hours=settings.price_age_warning_hours,
        stale_age_hours=settings.max_price_age_hours,
    )
    if status.status in {"stale", "broken"}:
        raise HTTPException(
            status_code=503,
            detail="active local PriceUniverse is not usable for consumer planning",
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
            saved.request.memberships or None,
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
        saved_context_ids = {
            group.store_id for group in saved.plan.optimized_basket.stores
        }
        unavailable_saved_context_ids = tuple(
            sorted(saved_context_ids - current_context_ids)
        )
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
        provenance.source_snapshot_id
        if provenance is not None
        else saved.price_universe_id
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

    if debug is not None:
        request = request.model_copy(update={"debug": debug})
    settings = get_settings()
    request = _production_consumer_request(request, settings)
    if settings.price_universe_required:
        _assert_offline_ready(request, settings)
    try:
        plan = _with_release(
            await _run_admitted_plan(request, http_request, settings),
            settings,
        )
        if settings.price_universe_required:
            _assert_offline_plan(plan)
        return plan
    except IncompleteBasketError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PriceProviderError as exc:
        raise HTTPException(status_code=502, detail="price provider unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/plans", response_model=SavedPlan, status_code=201)
async def create_saved_plan(request: PlanRequest, http_request: Request) -> SavedPlan:
    """Create and persist a reproducible, provider-offline consumer plan."""

    settings = get_settings()
    request = _production_consumer_request(request, settings)
    consumer_request = _consumer_request(request)
    _assert_offline_ready(consumer_request, settings)
    try:
        plan = _with_release(
            await _run_admitted_plan(consumer_request, http_request, settings),
            settings,
        )
        _assert_offline_plan(plan)
        return _annotate_freshness(
            _store(http_request).create(
                consumer_request,
                plan,
                owner_actor_hash=_plan_actor_hash(http_request, settings),
            )
        )
    except IncompleteBasketError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PriceProviderError as exc:
        raise HTTPException(status_code=502, detail="price provider unavailable") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
        plan = replace_product(
            saved.plan,
            saved.request,
            product_id=request.product_id,
            replacement_product_id=request.replacement_product_id,
        )
        plan = _with_release(plan, settings)
        return _annotate_freshness(
            store.append(
                plan_id=plan_id,
                request=saved.request,
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
        plan = await replace_recipe(
            saved.plan,
            saved.request,
            recipe_index=request.recipe_index,
            replacement_recipe_name=request.replacement_recipe_name,
            settings=settings,
        )
        plan = _with_release(plan, settings)
        return _annotate_freshness(
            store.append(
                plan_id=plan_id,
                request=saved.request,
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
