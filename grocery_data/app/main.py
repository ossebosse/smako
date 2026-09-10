from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from grocery_data.app.api import (
    catalog_router,
    community_evidence_router,
    health_router,
    operations_router,
    physical_check_router,
    price_context_router,
    registry_router,
    sources_router,
    store_coverage_router,
)
from grocery_data.app.config import GroceryDataSettings, load_repository_dotenv
from grocery_data.app.field_security import (
    FieldModeBoundaryMiddleware,
    FieldSecurityContext,
    field_login_router,
)
from grocery_data.app.services.prepared_universe_activation import (
    PreparedUniverseArtifactStore,
)
from grocery_data.app.storage import (
    SessionFactory,
    create_database_engine,
    create_schema,
    create_session_factory,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"


def _default_session_factory() -> tuple[SessionFactory, object]:
    """Create a usable default from the same repository config as the CLI."""

    load_repository_dotenv()
    engine = create_database_engine(GroceryDataSettings.from_env().database_url)
    create_schema(engine)
    return create_session_factory(engine), engine


def create_app(
    session_factory: SessionFactory | None = None,
    *,
    price_universe_manager: object | None = None,
    price_universe_artifact_store: PreparedUniverseArtifactStore | None = None,
    settings: GroceryDataSettings | None = None,
) -> FastAPI:
    settings = settings or GroceryDataSettings.from_env()
    owned_engine = None
    if session_factory is None:
        session_factory, owned_engine = _default_session_factory()

    application = FastAPI(
        title="Grocery Data",
        version="0.1.0",
        description="Replaybar matvaru-, pris- och connectorstatus för svenska kedjor.",
        docs_url=None if settings.field_mode_enabled else "/docs",
        redoc_url=None if settings.field_mode_enabled else "/redoc",
        openapi_url=None if settings.field_mode_enabled else "/openapi.json",
    )
    application.state.session_factory = session_factory
    application.state.owned_engine = owned_engine
    application.state.price_universe_manager = price_universe_manager
    application.state.price_universe_artifact_store = (
        price_universe_artifact_store
        or PreparedUniverseArtifactStore(
            settings.price_universe_cache_root
        )
    )
    application.state.settings = settings
    if settings.field_mode_enabled:
        application.state.field_security = FieldSecurityContext.from_settings(settings)
        application.include_router(field_login_router())
        application.include_router(physical_check_router)

        @application.get("/static/physical-check.css", include_in_schema=False)
        def physical_check_stylesheet() -> FileResponse:
            return FileResponse(STATIC_DIR / "physical-check.css", media_type="text/css")

        @application.get("/static/physical-check.js", include_in_schema=False)
        def physical_check_javascript() -> FileResponse:
            return FileResponse(
                STATIC_DIR / "physical-check.js",
                media_type="application/javascript",
            )

        @application.get(
            "/static/physical-check-api-errors.js",
            include_in_schema=False,
        )
        def physical_check_api_errors_javascript() -> FileResponse:
            return FileResponse(
                STATIC_DIR / "physical-check-api-errors.js",
                media_type="application/javascript",
            )

        @application.get(
            "/static/physical-barcode-scanner.js",
            include_in_schema=False,
        )
        def physical_barcode_scanner_javascript() -> FileResponse:
            return FileResponse(
                STATIC_DIR / "physical-barcode-scanner.js",
                media_type="application/javascript",
            )

        application.add_middleware(FieldModeBoundaryMiddleware)
        return application

    application.include_router(health_router)
    application.include_router(operations_router)
    # The static coverage route must precede catalog's /stores/{store_id} route.
    application.include_router(store_coverage_router)
    application.include_router(price_context_router)
    application.include_router(catalog_router)
    application.include_router(registry_router)
    application.include_router(sources_router)
    application.include_router(physical_check_router)
    application.include_router(community_evidence_router)
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.get("/", include_in_schema=False)
    def status_page() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @application.get("/admin/connectors/{chain}", include_in_schema=False)
    def connector_page(chain: str) -> FileResponse:
        del chain
        return FileResponse(STATIC_DIR / "connector.html")

    return application


app = create_app()
