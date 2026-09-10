from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from app.api.beta_ops import router as beta_ops_router
from app.api.plan import router as plan_router
from app.api.product_search import router as product_search_router
from app.config import Settings, get_settings
from app.services.beta_observability import BetaRequestMiddleware
from app.services.plan_prewarm import prewarm_active_price_universe
from app.services.plan_store import PlanStore
from app.services.planner_admission import PlannerAdmissionController
from app.services.price_universe_runtime import (
    GLOBAL_PREPARED_PRICE_UNIVERSES,
    PreparedPriceUniverse,
    PreparedPriceUniverseManager,
)
from app.services.pricing_projection_prewarm import precompute_pricing_semantics
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from grocery_data.app.api.community_evidence import install_community_evidence_api
from grocery_data.app.config import GroceryDataSettings

STATIC_DIR = Path(__file__).resolve().parent / "static"
SCANNER_BUNDLE = (
    Path(__file__).resolve().parents[2]
    / "grocery_data"
    / "app"
    / "static"
    / "physical-barcode-scanner.js"
)


def api_documentation_config(settings: Settings) -> dict[str, str | None]:
    """Keep interactive API discovery outside the public production surface."""

    if settings.app_env == "production":
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
    }


def load_configured_price_universe(
    settings: Settings,
    *,
    manager: PreparedPriceUniverseManager = GLOBAL_PREPARED_PRICE_UNIVERSES,
) -> PreparedPriceUniverse | None:
    """Load the hash-verified active artifact once at process startup.

    Collection/refresh owns manifest activation.  This composition boundary
    only resolves that immutable pointer and delegates full schema validation
    to the runtime loader; it never constructs products or calls a provider.
    """

    if not settings.price_universe_required:
        return None
    from grocery_data.app.services.prepared_universe_activation import (
        PreparedUniverseArtifactStore,
    )

    store = PreparedUniverseArtifactStore(settings.price_universe_cache_root)
    artifact = store.resolve_active_artifact(settings.price_universe_city)
    if artifact is None:
        raise RuntimeError("required active PriceUniverse artifact is unavailable")
    return manager.load_file_and_activate(artifact)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    application.state.beta_settings = settings
    application.state.plan_store = PlanStore(settings.plan_store_path)
    application.state.planner_admission = PlannerAdmissionController(
        max_concurrent=settings.planner_max_concurrent_requests,
        max_queued=settings.planner_max_queued_requests,
    )
    prepared = load_configured_price_universe(settings)
    # The selector-dependent but membership-independent semantic projection is
    # process-local. Build it after the immutable artifact is active so the
    # first unseen user request only performs its cheap eligibility projection.
    application.state.pricing_projection_prewarm = precompute_pricing_semantics(
        settings,
        prepared,
    )
    # This fills only process-local caches against the artifact activated
    # above.  It is disabled by default, makes no provider request and its
    # per-profile failure boundary never swaps or invalidates the universe.
    application.state.plan_prewarm = await prewarm_active_price_universe(settings)
    try:
        yield
    finally:
        community_engine = getattr(application.state, "community_evidence_engine", None)
        if community_engine is not None:
            community_engine.dispose()


_BOOT_SETTINGS = get_settings()

app = FastAPI(
    title="Billigaste veckomenyn",
    version=_BOOT_SETTINGS.app_version,
    description=(
        "Prisdriven svensk middagsplanering med deterministisk förpacknings- och butiksoptimering."
    ),
    lifespan=lifespan,
    **api_documentation_config(_BOOT_SETTINGS),
)
app.add_middleware(BetaRequestMiddleware, settings_factory=get_settings)
app.include_router(plan_router)
app.include_router(product_search_router)
app.include_router(beta_ops_router)
install_community_evidence_api(
    app,
    settings=GroceryDataSettings.from_env(),
    # Production schema changes are owned by Alembic. Keeping module import
    # read-only also prevents test collection from creating a database file.
    create_tables=False,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/manifest.webmanifest", include_in_schema=False)
async def web_app_manifest() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "manifest.webmanifest",
        media_type="application/manifest+json",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/service-worker.js", include_in_schema=False)
async def service_worker() -> FileResponse:
    """Serve the worker at the origin root without caching the worker itself."""

    return FileResponse(
        STATIC_DIR / "service-worker.js",
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Service-Worker-Allowed": "/",
        },
    )


@app.get("/scanner-assets/physical-barcode-scanner.js", include_in_schema=False)
async def physical_barcode_scanner() -> FileResponse:
    """Serve the existing local-only ZXing scanner bundle to the consumer UI."""

    return FileResponse(SCANNER_BUNDLE, media_type="application/javascript")
