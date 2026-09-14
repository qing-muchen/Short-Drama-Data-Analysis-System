"""Versioned API routers for the basic CRUD baseline."""

from fastapi import APIRouter

from routers import (
    actors,
    analytics,
    dashboard,
    auth,
    companies,
    directors,
    dramas,
    imports,
    platforms,
    scores,
    tags,
    users,
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(auth.router)
api_v1_router.include_router(analytics.router)
api_v1_router.include_router(dashboard.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(dramas.router)
api_v1_router.include_router(actors.router)
api_v1_router.include_router(directors.router)
api_v1_router.include_router(companies.router)
api_v1_router.include_router(platforms.router)
api_v1_router.include_router(tags.router)
api_v1_router.include_router(imports.router)
api_v1_router.include_router(scores.router)

__all__ = ["api_v1_router"]
