"""Versioned API routers for the basic CRUD baseline."""

from fastapi import APIRouter

from routers import (
    actors,
    anomaly,
    operation_action,
    operation_analytics,
    analytics,
    dashboard,
    drama_profile,
    auth,
    companies,
    data_governance,
    data_quality,
    explanation,
    directors,
    dramas,
    imports,
    import_batches,
    platforms,
    prediction,
    scores,
    tags,
    users,
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth.router)
api_v1_router.include_router(analytics.router)
api_v1_router.include_router(dashboard.router)
api_v1_router.include_router(operation_analytics.router)
api_v1_router.include_router(drama_profile.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(dramas.router)
api_v1_router.include_router(actors.router)
api_v1_router.include_router(directors.router)
api_v1_router.include_router(companies.router)
api_v1_router.include_router(platforms.router)
api_v1_router.include_router(tags.router)
api_v1_router.include_router(imports.router)
api_v1_router.include_router(import_batches.router)
api_v1_router.include_router(scores.router)
api_v1_router.include_router(prediction.router)
api_v1_router.include_router(data_governance.router)
api_v1_router.include_router(data_quality.router)
api_v1_router.include_router(anomaly.router)
api_v1_router.include_router(operation_action.router)
api_v1_router.include_router(explanation.router)
api_v1_router.include_router(explanation.lineage_router)

__all__ = ["api_v1_router"]
