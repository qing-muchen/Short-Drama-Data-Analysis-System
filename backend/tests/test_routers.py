"""Router, OpenAPI, response, and exception tests using isolated Services."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from httpx import ASGITransport, AsyncClient

from auth.dependencies import get_current_user
from main import app
from routers.dependencies import get_drama_service
from services.exceptions import ConflictException, NotFoundException, PersistenceException


def _drama(*, status: str = "DRAFT") -> SimpleNamespace:
    now = datetime.now(UTC).replace(tzinfo=None)
    return SimpleNamespace(
        drama_id=1,
        drama_code="DRM000001",
        drama_name="Sample Drama",
        synopsis=None,
        episode_count=24,
        episode_duration_seconds=120,
        premiere_date=None,
        status=status,
        created_at=now,
        updated_at=now,
    )


def _identity(role: str = "ADMINISTRATOR") -> SimpleNamespace:
    return SimpleNamespace(role_code=role, status="ACTIVE")


class FakeDramaService:
    """Service-shaped test double; no Session or database is created."""

    def list_dramas(self, **filters: Any) -> SimpleNamespace:
        return SimpleNamespace(
            page=filters["page"],
            page_size=filters["page_size"],
            total=1,
            items=[_drama()],
        )

    def get_drama(self, _drama_id: int) -> SimpleNamespace:
        return _drama()

    def create_drama(self, _values: dict[str, Any]) -> SimpleNamespace:
        return _drama()

    def update_drama(
        self,
        _drama_id: int,
        _values: dict[str, Any],
    ) -> SimpleNamespace:
        return _drama(status="COMPLETED")

    def deactivate_drama(self, _drama_id: int) -> SimpleNamespace:
        return _drama(status="INACTIVE")


def _request(method: str, path: str, **kwargs: Any) -> tuple[int, Any]:
    async def perform() -> tuple[int, Any]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.request(method, path, **kwargs)
            content_type = response.headers.get("content-type", "")
            body = response.json() if "application/json" in content_type else response.text
            return response.status_code, body

    return asyncio.run(perform())


def test_openapi_registers_only_authorized_basic_api_paths() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    crud_resources = ("dramas", "actors", "directors", "companies", "platforms", "tags")

    for resource in crud_resources:
        assert set(paths[f"/api/v1/{resource}"]) == {"get", "post"}
        item_path = next(path for path in paths if path.startswith(f"/api/v1/{resource}/"))
        assert set(paths[item_path]) == {"get", "put", "delete"}

    assert set(paths["/api/v1/users"]) == {"get"}
    assert set(paths["/api/v1/users/{user_id}"]) == {"get"}
    assert set(paths["/api/v1/auth/login"]) == {"post"}
    assert set(paths["/api/v1/auth/me"]) == {"get"}
    assert set(paths["/api/v1/import/jobs"]) == {"post"}
    assert set(paths["/api/v1/import/jobs/{import_job_id}"]) == {"get"}
    assert set(paths["/api/v1/import/jobs/{import_job_id}/errors"]) == {"get"}
    assert set(paths["/api/v1/import/jobs/{import_job_id}/confirm"]) == {"post"}
    assert set(paths["/api/v1/analytics/dramas/{drama_id}/summary"]) == {"get"}
    assert set(paths["/api/v1/dashboard/overview"]) == {"get"}
    assert set(paths["/api/v1/dashboard/rankings/heat"]) == {"get"}
    assert set(paths["/api/v1/dashboard/rankings/growth"]) == {"get"}
    assert set(paths["/api/v1/dashboard/rankings/potential"]) == {"get"}
    assert set(paths["/api/v1/dashboard/trend"]) == {"get"}
    assert set(paths["/api/v1/dashboard/quality"]) == {"get"}
    assert set(paths["/api/v1/scores/calculate"]) == {"post"}
    assert set(paths["/api/v1/scores/ranking"]) == {"get"}
    assert set(paths["/api/v1/scores/level-distribution"]) == {"get"}
    assert set(paths["/api/v1/scores/{drama_id}"]) == {"get"}
    drama_errors = paths["/api/v1/dramas/{drama_id}"]["get"]["responses"]
    assert drama_errors["404"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/ErrorResponse"
    )


def test_docs_and_openapi_are_available_without_database_access() -> None:
    docs_status, docs_body = _request("GET", "/docs")
    schema_status, schema_body = _request("GET", "/openapi.json")

    assert docs_status == 200
    assert "Swagger UI" in docs_body
    assert schema_status == 200
    assert schema_body["info"]["version"] == "0.1.0"


def test_drama_crud_uses_schema_envelopes_with_service_override() -> None:
    app.dependency_overrides[get_drama_service] = FakeDramaService
    app.dependency_overrides[get_current_user] = _identity
    try:
        list_status, list_body = _request("GET", "/api/v1/dramas?page=1&page_size=20")
        detail_status, detail_body = _request("GET", "/api/v1/dramas/1")
        create_status, create_body = _request(
            "POST",
            "/api/v1/dramas",
            json={"drama_name": "Sample Drama", "episode_count": 24},
        )
        update_status, update_body = _request(
            "PUT",
            "/api/v1/dramas/1",
            json={"status": "COMPLETED"},
        )
        delete_status, delete_body = _request("DELETE", "/api/v1/dramas/1")
    finally:
        app.dependency_overrides.clear()

    assert list_status == 200
    assert list_body["message"] == "success"
    assert list_body["data"]["total"] == 1
    assert list_body["data"]["items"][0]["drama_code"] == "DRM000001"
    assert detail_status == 200 and detail_body["data"]["drama_id"] == 1
    assert create_status == 201 and create_body["data"]["drama_name"] == "Sample Drama"
    assert update_status == 200 and update_body["data"]["status"] == "COMPLETED"
    assert delete_status == 200 and delete_body["data"]["status"] == "INACTIVE"


def test_service_exceptions_map_to_safe_error_response() -> None:
    class MissingDramaService(FakeDramaService):
        def get_drama(self, _drama_id: int) -> SimpleNamespace:
            raise NotFoundException("Drama was not found", details={"drama_id": 9})

        def create_drama(self, _values: dict[str, Any]) -> SimpleNamespace:
            raise ConflictException("Drama conflicts with existing data")

    app.dependency_overrides[get_drama_service] = MissingDramaService
    app.dependency_overrides[get_current_user] = _identity
    try:
        missing_status, missing_body = _request("GET", "/api/v1/dramas/9")
        conflict_status, conflict_body = _request(
            "POST",
            "/api/v1/dramas",
            json={"drama_name": "Sample Drama"},
        )
    finally:
        app.dependency_overrides.clear()

    assert missing_status == 404
    assert missing_body == {
        "code": "NOT_FOUND",
        "message": "Drama was not found",
        "details": {"drama_id": 9},
    }
    assert conflict_status == 409
    assert conflict_body["code"] == "BUSINESS_CONFLICT"
    assert "traceback" not in str(conflict_body).lower()


def test_persistence_exception_maps_to_safe_500_response() -> None:
    class FailedReadService(FakeDramaService):
        def get_drama(self, _drama_id: int) -> SimpleNamespace:
            raise PersistenceException()

    app.dependency_overrides[get_drama_service] = FailedReadService
    app.dependency_overrides[get_current_user] = _identity
    try:
        status_code, body = _request("GET", "/api/v1/dramas/1")
    finally:
        app.dependency_overrides.clear()

    assert status_code == 500
    assert body == {
        "code": "PERSISTENCE_ERROR",
        "message": "The data operation could not be completed",
        "details": None,
    }


def test_request_validation_uses_error_response() -> None:
    app.dependency_overrides[get_current_user] = _identity
    try:
        status_code, body = _request("GET", "/api/v1/dramas?page=0")
    finally:
        app.dependency_overrides.clear()

    assert status_code == 422
    assert body["code"] == "REQUEST_VALIDATION_ERROR"
    assert body["message"] == "Request validation failed"


def test_route_handlers_do_not_access_repository_or_orm_layers() -> None:
    router_path = Path(__file__).parents[1] / "routers"
    route_files = (
        "auth.py",
        "users.py",
        "dramas.py",
        "actors.py",
        "directors.py",
        "companies.py",
        "platforms.py",
        "tags.py",
        "imports.py",
        "analytics.py",
        "dashboard.py",
        "scores.py",
    )
    source = "\n".join(
        (router_path / file_name).read_text(encoding="utf-8")
        for file_name in route_files
    )

    assert "repositories" not in source
    assert "from models" not in source
    assert "import models" not in source
    assert ".session" not in source
