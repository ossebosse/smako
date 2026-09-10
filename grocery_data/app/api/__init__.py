from grocery_data.app.api.catalog import router as catalog_router
from grocery_data.app.api.community_evidence import router as community_evidence_router
from grocery_data.app.api.health import router as health_router
from grocery_data.app.api.operations import router as operations_router
from grocery_data.app.api.physical_check import router as physical_check_router
from grocery_data.app.api.price_contexts import router as price_context_router
from grocery_data.app.api.registry import router as registry_router
from grocery_data.app.api.sources import router as sources_router
from grocery_data.app.api.store_coverage import router as store_coverage_router

__all__ = [
    "catalog_router",
    "community_evidence_router",
    "health_router",
    "operations_router",
    "physical_check_router",
    "price_context_router",
    "registry_router",
    "sources_router",
    "store_coverage_router",
]
