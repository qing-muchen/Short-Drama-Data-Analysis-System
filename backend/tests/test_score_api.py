"""Score API schema, authorization, delegation, and error mapping tests."""

import asyncio
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from httpx import ASGITransport, AsyncClient

from auth.dependencies import get_current_user
from main import app
from repositories.base import Page
from routers.dependencies import get_score_service
from services.exceptions import PersistenceException, ValidationException

SCORE_DATE = date(2026, 9, 14)
ANALYSIS_AS_OF = datetime(2026, 9, 14, 12, 0)


def _identity(role: str = "ADMINISTRATOR") -> SimpleNamespace:
    return SimpleNamespace(user_id=7, role_code=role, status="ACTIVE")


def _score(drama_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        score_id=drama_id,
        drama_id=drama_id,
        drama=SimpleNamespace(
            drama_code=f"DRM{drama_id:06d}",
            drama_name=f"Drama {drama_id}",
        ),
        score_date=SCORE_DATE,
        score_scope_type="ALL",
        score_scope_id=0,
        analysis_as_of=ANALYSIS_AS_OF,
        heat_score=Decimal("88.50"),
        growth_score=Decimal("77.25"),
        engagement_score=Decimal("66.00"),
        lifecycle_score=Decimal("80.00"),
        total_score=Decimal("79.78"),
        level="A",
        algorithm_version="Composite Score V1.0",
        created_at=ANALYSIS_AS_OF,
        updated_at=ANALYSIS_AS_OF,
    )


class FakeScoreService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.ranking = Page(
            page=1,
            page_size=20,
            total=1,
            items=[_score()],
        )
        self.drama_score: Any | None = _score()
        self.distribution = {"S": 1, "A": 2, "B": 3, "C": 4}

    def calculate_scores(self, *args: Any, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(("calculate_scores", args, kwargs))
        return SimpleNamespace(
            score_date=args[0],
            analysis_as_of=ANALYSIS_AS_OF,
            algorithm_version="Composite Score V1.0",
            score_scope_type="ALL",
            score_scope_id=0,
            calculated_count=90,
            skipped_count=10,
            skipped_reasons={"INSUFFICIENT_HISTORY": 10},
        )

    def get_ranking(self, *args: Any, **kwargs: Any) -> Page[Any]:
        self.calls.append(("get_ranking", args, kwargs))
        return self.ranking

    def get_drama_score(self, *args: Any, **kwargs: Any) -> Any | None:
        self.calls.append(("get_drama_score", args, kwargs))
        return self.drama_score

    def get_level_distribution(self, *args: Any, **kwargs: Any) -> dict[str, int]:
        self.calls.append(("get_level_distribution", args, kwargs))
        return self.distribution


def _request(method: str, path: str, **kwargs: Any) -> tuple[int, Any]:
    async def perform() -> tuple[int, Any]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.request(method, path, **kwargs)
            return response.status_code, response.json()

    return asyncio.run(perform())


def _override(service: FakeScoreService, *, role: str = "ADMINISTRATOR") -> None:
    app.dependency_overrides[get_score_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: _identity(role)


def test_openapi_registers_score_paths_with_jwt_bearer() -> None:
    schema = app.openapi()
    paths = schema["paths"]

    assert set(paths["/api/v1/scores/calculate"]) == {"post"}
    assert set(paths["/api/v1/scores/ranking"]) == {"get"}
    assert set(paths["/api/v1/scores/level-distribution"]) == {"get"}
    assert set(paths["/api/v1/scores/{drama_id}"]) == {"get"}
    for path, method in (
        ("/api/v1/scores/calculate", "post"),
        ("/api/v1/scores/ranking", "get"),
        ("/api/v1/scores/level-distribution", "get"),
        ("/api/v1/scores/{drama_id}", "get"),
    ):
        operation = paths[path][method]
        assert operation["security"] == [{"JWTBearer": []}]
        error_schema = operation["responses"]["500"]["content"][
            "application/json"
        ]["schema"]
        assert error_schema["$ref"].endswith("/ErrorResponse")


def test_calculate_requires_admin_and_passes_identity_to_service() -> None:
    service = FakeScoreService()
    _override(service)
    try:
        status_code, body = _request(
            "POST",
            "/api/v1/scores/calculate",
            json={"score_date": SCORE_DATE.isoformat()},
        )
    finally:
        app.dependency_overrides.clear()

    assert status_code == 200
    assert service.calls == [
        ("calculate_scores", (SCORE_DATE,), {"administrator_id": 7})
    ]
    assert body["message"] == "success"
    assert body["data"]["calculated_count"] == 90
    assert body["data"]["skipped_count"] == 10
    assert body["data"]["score_scope_type"] == "ALL"
    assert body["data"]["score_scope_id"] == 0


def test_anonymous_is_401_and_user_calculation_is_403() -> None:
    service = FakeScoreService()
    app.dependency_overrides[get_score_service] = lambda: service
    try:
        anonymous_status, anonymous_body = _request(
            "POST",
            "/api/v1/scores/calculate",
            json={"score_date": SCORE_DATE.isoformat()},
        )
        app.dependency_overrides[get_current_user] = lambda: _identity("USER")
        user_status, user_body = _request(
            "POST",
            "/api/v1/scores/calculate",
            json={"score_date": SCORE_DATE.isoformat()},
        )
    finally:
        app.dependency_overrides.clear()

    assert anonymous_status == 401
    assert anonymous_body["code"] == "AUTHENTICATION_FAILED"
    assert user_status == 403
    assert user_body["code"] == "FORBIDDEN"
    assert service.calls == []


def test_authenticated_user_gets_paginated_filtered_ranking() -> None:
    service = FakeScoreService()
    service.ranking = Page(
        page=2,
        page_size=2,
        total=4,
        items=[_score(3), _score(4)],
    )
    _override(service, role="USER")
    try:
        status_code, body = _request(
            "GET",
            "/api/v1/scores/ranking"
            f"?score_date={SCORE_DATE.isoformat()}&page=2&page_size=2&level=A",
        )
    finally:
        app.dependency_overrides.clear()

    assert status_code == 200
    assert service.calls == [
        (
            "get_ranking",
            (SCORE_DATE,),
            {"page": 2, "page_size": 2, "level": "A"},
        )
    ]
    data = body["data"]
    assert (data["page"], data["page_size"], data["total"]) == (2, 2, 4)
    assert [item["rank"] for item in data["items"]] == [3, 4]
    assert [item["drama_id"] for item in data["items"]] == [3, 4]
    assert data["items"][0]["total_score"] == 79.78


def test_level_distribution_is_static_route_and_has_fixed_order() -> None:
    service = FakeScoreService()
    _override(service, role="USER")
    try:
        status_code, body = _request(
            "GET",
            "/api/v1/scores/level-distribution"
            f"?score_date={SCORE_DATE.isoformat()}",
        )
    finally:
        app.dependency_overrides.clear()

    assert status_code == 200
    assert service.calls == [("get_level_distribution", (SCORE_DATE,), {})]
    assert body["data"]["total"] == 10
    assert body["data"]["items"] == [
        {"level": "S", "count": 1},
        {"level": "A", "count": 2},
        {"level": "B", "count": 3},
        {"level": "C", "count": 4},
    ]


def test_drama_score_detail_and_not_found_response() -> None:
    service = FakeScoreService()
    _override(service, role="USER")
    try:
        success_status, success_body = _request("GET", "/api/v1/scores/1")
        service.drama_score = None
        missing_status, missing_body = _request("GET", "/api/v1/scores/9")
    finally:
        app.dependency_overrides.clear()

    assert success_status == 200
    assert success_body["data"]["drama_code"] == "DRM000001"
    assert missing_status == 404
    assert missing_body == {
        "code": "NOT_FOUND",
        "message": "Drama score was not found",
        "details": {"drama_id": 9},
    }


def test_score_request_and_query_validation_return_422() -> None:
    service = FakeScoreService()
    _override(service)
    try:
        requests = (
            _request("GET", "/api/v1/scores/ranking?page=1"),
            _request(
                "GET",
                f"/api/v1/scores/ranking?score_date={SCORE_DATE}&page=0",
            ),
            _request(
                "GET",
                f"/api/v1/scores/ranking?score_date={SCORE_DATE}&page_size=101",
            ),
            _request(
                "GET",
                f"/api/v1/scores/ranking?score_date={SCORE_DATE}&level=D",
            ),
            _request("GET", "/api/v1/scores/0"),
            _request(
                "POST",
                "/api/v1/scores/calculate",
                json={
                    "score_date": SCORE_DATE.isoformat(),
                    "algorithm_version": "client-controlled",
                    "scope_type": "TAG",
                    "scope_id": 1,
                },
            ),
        )
    finally:
        app.dependency_overrides.clear()

    assert all(status_code == 422 for status_code, _ in requests)
    assert all(body["code"] == "REQUEST_VALIDATION_ERROR" for _, body in requests)
    assert service.calls == []


def test_service_business_and_persistence_errors_use_global_mapping() -> None:
    class FailedScoreService(FakeScoreService):
        def calculate_scores(self, *args: Any, **kwargs: Any) -> Any:
            raise ValidationException("Score date cannot be in the future")

        def get_ranking(self, *args: Any, **kwargs: Any) -> Page[Any]:
            raise PersistenceException()

    service = FailedScoreService()
    _override(service)
    try:
        validation_status, validation_body = _request(
            "POST",
            "/api/v1/scores/calculate",
            json={"score_date": SCORE_DATE.isoformat()},
        )
        persistence_status, persistence_body = _request(
            "GET",
            f"/api/v1/scores/ranking?score_date={SCORE_DATE}",
        )
    finally:
        app.dependency_overrides.clear()

    assert validation_status == 400
    assert validation_body["code"] == "VALIDATION_ERROR"
    assert persistence_status == 500
    assert persistence_body == {
        "code": "PERSISTENCE_ERROR",
        "message": "The data operation could not be completed",
        "details": None,
    }
