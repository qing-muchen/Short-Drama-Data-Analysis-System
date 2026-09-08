"""FastAPI application entry point."""

from fastapi import FastAPI

from config.settings import get_settings
from routers import api_v1_router
from routers.errors import install_exception_handlers

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
)
app.include_router(api_v1_router)
install_exception_handlers(app)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Return the process health state without touching business data."""

    return {"status": "ok"}
