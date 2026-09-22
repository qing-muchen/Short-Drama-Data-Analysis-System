"""API tests for read-only explanation and lineage queries."""

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from httpx import ASGITransport, AsyncClient

from auth.dependencies import get_current_user
from main import app
from routers.dependencies import get_explanation_query_service


AS_OF = datetime(2026, 9, 22, tzinfo=timezone.utc)


def identity() -> SimpleNamespace:
    return SimpleNamespace(user_id=3, role_code="USER", status="ACTIVE")


def explanation() -> SimpleNamespace:
    return SimpleNamespace(
        explanation_id=1,
        entity_type="SCORE",
        entity_id=10,
        module_type="SCORE",
        summary="增长相对较弱。",
        detail={"reason": "增长相对较弱。", "inputs": [], "rules": [], "versions": {}, "evidence": []},
        algorithm_version="Composite Score V1.0",
        rule_set_version="N/A",
        analysis_as_of=AS_OF,
        created_at=AS_OF,
    )


def lineage() -> SimpleNamespace:
    return SimpleNamespace(
        lineage_id=2,
        target_type="EXPLANATION",
        target_id=1,
        source_type="METRIC",
        source_id=10,
        relationship_type="DERIVED_FROM",
        analysis_as_of=AS_OF,
        created_at=AS_OF,
    )


class FakeQueryService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_explanations(self, **kwargs: Any) -> Any:
        self.calls.append(("get_explanations", kwargs))
        return SimpleNamespace(page=kwargs["page"], page_size=kwargs["page_size"], total=1, items=[explanation()])

    def get_lineage(self, **kwargs: Any) -> Any:
        self.calls.append(("get_lineage", kwargs))
        return SimpleNamespace(page=kwargs["page"], page_size=kwargs["page_size"], total=1, items=[lineage()])


def request(method: str, path: str, **kwargs: Any) -> tuple[int, Any]:
    async def perform() -> tuple[int, Any]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.request(method, path, **kwargs)
            return response.status_code, response.json()

    return asyncio.run(perform())


def override(service: FakeQueryService) -> None:
    app.dependency_overrides[get_explanation_query_service] = lambda: service
    app.dependency_overrides[get_current_user] = identity


def test_openapi_registers_explanation_and_lineage_paths_with_bearer() -> None:
    paths = app.openapi()["paths"]
    assert set(paths["/api/v1/explanations/{entity_type}/{entity_id}"]) == {"get"}
    assert set(paths["/api/v1/lineage/{target_type}/{target_id}"]) == {"get"}
    for path in (
        "/api/v1/explanations/{entity_type}/{entity_id}",
        "/api/v1/lineage/{target_type}/{target_id}",
    ):
        assert paths[path]["get"]["security"] == [{"JWTBearer": []}]


def test_authenticated_explanation_query_delegates_filters_and_page() -> None:
    service = FakeQueryService()
    override(service)
    try:
        status, body = request(
            "GET",
            "/api/v1/explanations/SCORE/10?module_type=SCORE&analysis_as_of="
            "2026-09-22T00:00:00Z&algorithm_version=Composite%20Score%20V1.0"
            "&rule_set_version=N%2FA&page=2&page_size=5",
        )
    finally:
        app.dependency_overrides.clear()

    assert status == 200
    assert body["data"]["page"] == 2
    assert body["data"]["items"][0]["explanation_id"] == 1
    assert service.calls[0][0] == "get_explanations"
    assert service.calls[0][1]["page_size"] == 5
    assert service.calls[0][1]["algorithm_version"] == "Composite Score V1.0"


def test_authenticated_lineage_query_delegates_filters_and_page() -> None:
    service = FakeQueryService()
    override(service)
    try:
        status, body = request(
            "GET",
            "/api/v1/lineage/EXPLANATION/1?source_type=METRIC"
            "&relationship_type=DERIVED_FROM&page=1&page_size=10",
        )
    finally:
        app.dependency_overrides.clear()

    assert status == 200
    assert body["data"]["items"][0]["source_type"] == "METRIC"
    assert service.calls[0][1]["relationship_type"] == "DERIVED_FROM"


def test_anonymous_queries_return_401() -> None:
    service = FakeQueryService()
    app.dependency_overrides[get_explanation_query_service] = lambda: service
    try:
        status, body = request("GET", "/api/v1/explanations/SCORE/10")
    finally:
        app.dependency_overrides.clear()

    assert status == 401
    assert body["code"] == "AUTHENTICATION_FAILED"
    assert service.calls == []


def test_invalid_path_and_pagination_return_422_without_service_call() -> None:
    service = FakeQueryService()
    override(service)
    try:
        responses = (
            request("GET", "/api/v1/explanations/UNKNOWN/0"),
            request("GET", "/api/v1/lineage/EXPLANATION/1?page_size=101"),
        )
    finally:
        app.dependency_overrides.clear()

    assert all(status == 422 for status, _ in responses)
    assert service.calls == []
