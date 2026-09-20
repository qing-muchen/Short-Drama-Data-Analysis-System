"""Anomaly API schema, authorization, delegation, and error tests."""

import asyncio
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from httpx import ASGITransport, AsyncClient

from auth.dependencies import get_current_user
from main import app
from repositories.base import Page
from routers.dependencies import get_anomaly_service
from services.exceptions import PersistenceException, ValidationException


ANALYSIS_AS_OF = datetime(2026, 9, 20, 0, 0)


def _identity(role: str = "ADMINISTRATOR") -> SimpleNamespace:
    return SimpleNamespace(user_id=7, role_code=role, status="ACTIVE")


def _anomaly(anomaly_id: int = 1) -> SimpleNamespace:
    now = ANALYSIS_AS_OF
    return SimpleNamespace(
        anomaly_id=anomaly_id,
        drama_id=7,
        drama=SimpleNamespace(drama_code="DRM000007", drama_name="Sample Drama"),
        metric_type="PLAY_COUNT",
        anomaly_type="PLAY_COUNT_GROWTH_ANOMALY",
        severity="A",
        status="OPEN",
        analysis_as_of=ANALYSIS_AS_OF,
        algorithm_version="Rule-based Detection V1.0",
        evidence_summary="current_value=260; baseline_mean=100; z_score=4",
        created_at=now,
        updated_at=now,
    )


class FakeAnomalyService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.page = Page(page=1, page_size=20, total=1, items=[_anomaly()])
        self.drama_items: list[Any] = [_anomaly()]
        self.statistics = SimpleNamespace(
            total_count=4,
            severity_distribution={"A": 1, "B": 2, "C": 1},
            status_distribution={
                "OPEN": 3,
                "ACKNOWLEDGED": 1,
                "RESOLVED": 0,
                "IGNORED": 0,
            },
            metric_distribution={"PLAY_COUNT": 3, "ENGAGEMENT_RATE": 1},
        )

    def detect_anomalies(self, *args: Any, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(("detect_anomalies", args, kwargs))
        return SimpleNamespace(
            analysis_as_of=args[0] or ANALYSIS_AS_OF,
            algorithm_version="Rule-based Detection V1.0",
            detected_count=2,
            skipped_count=1,
            skip_reasons={"INSUFFICIENT_HISTORY": 1},
        )

    def get_anomalies(self, **kwargs: Any) -> Page[Any]:
        self.calls.append(("get_anomalies", (), kwargs))
        return self.page

    def get_drama_anomalies(self, drama_id: int, **kwargs: Any) -> list[Any]:
        self.calls.append(("get_drama_anomalies", (drama_id,), kwargs))
        return self.drama_items

    def get_statistics(self) -> Any:
        self.calls.append(("get_statistics", (), {}))
        return self.statistics

    def update_status(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(("update_status", args, kwargs))
        entity = _anomaly()
        entity.status = args[1]
        return entity


def _request(method: str, path: str, **kwargs: Any) -> tuple[int, Any]:
    async def perform() -> tuple[int, Any]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.request(method, path, **kwargs)
            return response.status_code, response.json()

    return asyncio.run(perform())


def _override(service: FakeAnomalyService, *, role: str = "ADMINISTRATOR") -> None:
    app.dependency_overrides[get_anomaly_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: _identity(role)


def test_openapi_registers_static_anomaly_paths_with_jwt_bearer() -> None:
    paths = app.openapi()["paths"]
    assert set(paths["/api/v1/anomalies/detect"]) == {"post"}
    assert set(paths["/api/v1/anomalies/statistics"]) == {"get"}
    assert set(paths["/api/v1/anomalies"]) == {"get"}
    assert set(paths["/api/v1/anomalies/{drama_id}"]) == {"get"}
    assert set(paths["/api/v1/anomalies/{record_id}/status"]) == {"patch"}
    for path, method in (
        ("/api/v1/anomalies/detect", "post"),
        ("/api/v1/anomalies", "get"),
        ("/api/v1/anomalies/statistics", "get"),
        ("/api/v1/anomalies/{drama_id}", "get"),
        ("/api/v1/anomalies/{record_id}/status", "patch"),
    ):
        operation = paths[path][method]
        assert operation["security"] == [{"JWTBearer": []}]
        assert operation["responses"]["500"]["content"][
            "application/json"
        ]["schema"]["$ref"].endswith("/ErrorResponse")


def test_admin_detect_passes_analysis_as_of_and_returns_envelope() -> None:
    service = FakeAnomalyService()
    _override(service)
    try:
        status, body = _request(
            "POST",
            "/api/v1/anomalies/detect",
            json={"analysis_as_of": ANALYSIS_AS_OF.isoformat()},
        )
    finally:
        app.dependency_overrides.clear()

    assert status == 200
    assert service.calls == [
        (
            "detect_anomalies",
            (ANALYSIS_AS_OF,),
            {"operator_user_id": 7},
        )
    ]
    assert body["message"] == "success"
    assert body["data"]["detected_count"] == 2
    assert body["data"]["algorithm_version"] == "Rule-based Detection V1.0"


def test_anonymous_is_401_and_user_detect_is_403() -> None:
    service = FakeAnomalyService()
    app.dependency_overrides[get_anomaly_service] = lambda: service
    try:
        anonymous_status, anonymous_body = _request(
            "POST",
            "/api/v1/anomalies/detect",
            json={},
        )
        app.dependency_overrides[get_current_user] = lambda: _identity("USER")
        user_status, user_body = _request(
            "POST",
            "/api/v1/anomalies/detect",
            json={},
        )
    finally:
        app.dependency_overrides.clear()

    assert anonymous_status == 401
    assert anonymous_body["code"] == "AUTHENTICATION_FAILED"
    assert user_status == 403
    assert user_body["code"] == "FORBIDDEN"
    assert service.calls == []


def test_user_lists_anomalies_with_pagination_and_filters() -> None:
    service = FakeAnomalyService()
    _override(service, role="USER")
    try:
        status, body = _request(
            "GET",
            "/api/v1/anomalies"
            f"?analysis_as_of={ANALYSIS_AS_OF.isoformat()}"
            "&metric_type=PLAY_COUNT&anomaly_type=PLAY_COUNT_GROWTH_ANOMALY"
            "&severity=A&status=OPEN&page=2&page_size=10",
        )
    finally:
        app.dependency_overrides.clear()

    assert status == 200
    assert service.calls == [
        (
            "get_anomalies",
            (),
            {
                "analysis_as_of": ANALYSIS_AS_OF,
                "metric_type": "PLAY_COUNT",
                "anomaly_type": "PLAY_COUNT_GROWTH_ANOMALY",
                "severity": "A",
                "status": "OPEN",
                "page": 2,
                "page_size": 10,
            },
        )
    ]
    assert body["data"]["items"][0]["record_id"] == 1
    assert body["data"]["items"][0]["drama_code"] == "DRM000007"


def test_drama_anomalies_and_statistics_are_available_to_users() -> None:
    service = FakeAnomalyService()
    _override(service, role="USER")
    try:
        drama_status, drama_body = _request("GET", "/api/v1/anomalies/7")
        statistics_status, statistics_body = _request(
            "GET", "/api/v1/anomalies/statistics"
        )
    finally:
        app.dependency_overrides.clear()

    assert drama_status == 200
    assert drama_body["data"][0]["status"] == "OPEN"
    assert statistics_status == 200
    assert statistics_body["data"]["total_count"] == 4
    assert statistics_body["data"]["severity_distribution"]["A"] == 1
    assert statistics_body["data"]["type_distribution"]["PLAY_COUNT"] == 3


def test_drama_anomalies_not_found_maps_to_404() -> None:
    service = FakeAnomalyService()
    service.drama_items = []
    _override(service, role="USER")
    try:
        status, body = _request("GET", "/api/v1/anomalies/99")
    finally:
        app.dependency_overrides.clear()

    assert status == 404
    assert body["code"] == "NOT_FOUND"
    assert body["details"] == {"drama_id": 99}


def test_admin_status_update_passes_status_and_operator() -> None:
    service = FakeAnomalyService()
    _override(service)
    try:
        status, body = _request(
            "PATCH",
            "/api/v1/anomalies/9/status",
            json={"status": "ACKNOWLEDGED"},
        )
    finally:
        app.dependency_overrides.clear()

    assert status == 200
    assert service.calls == [
        (
            "update_status",
            (9, "ACKNOWLEDGED"),
            {"operator_user_id": 7},
        )
    ]
    assert body["data"]["status"] == "ACKNOWLEDGED"


def test_user_status_update_is_forbidden() -> None:
    service = FakeAnomalyService()
    _override(service, role="USER")
    try:
        status, body = _request(
            "PATCH",
            "/api/v1/anomalies/9/status",
            json={"status": "ACKNOWLEDGED"},
        )
    finally:
        app.dependency_overrides.clear()

    assert status == 403
    assert body["code"] == "FORBIDDEN"
    assert service.calls == []


def test_validation_rejects_client_algorithm_fields_and_invalid_filters() -> None:
    service = FakeAnomalyService()
    _override(service)
    try:
        responses = (
            _request(
                "POST",
                "/api/v1/anomalies/detect",
                json={
                    "analysis_as_of": ANALYSIS_AS_OF.isoformat(),
                    "algorithm_version": "client-controlled",
                },
            ),
            _request("GET", "/api/v1/anomalies?page=0"),
            _request("GET", "/api/v1/anomalies?page_size=101"),
            _request("GET", "/api/v1/anomalies?severity=D"),
            _request("PATCH", "/api/v1/anomalies/0/status", json={"status": "OPEN"}),
        )
    finally:
        app.dependency_overrides.clear()

    assert all(status == 422 for status, _ in responses)
    assert all(body["code"] == "REQUEST_VALIDATION_ERROR" for _, body in responses)
    assert service.calls == []


def test_service_errors_use_global_error_response_mapping() -> None:
    class FailedAnomalyService(FakeAnomalyService):
        def detect_anomalies(self, *args: Any, **kwargs: Any) -> Any:
            raise ValidationException(
                "Anomaly analysis failed",
                details={"reason": "DATA_QUALITY_BLOCKED"},
            )

        def get_statistics(self) -> Any:
            raise PersistenceException()

    service = FailedAnomalyService()
    _override(service)
    try:
        validation_status, validation_body = _request(
            "POST",
            "/api/v1/anomalies/detect",
            json={},
        )
        persistence_status, persistence_body = _request(
            "GET", "/api/v1/anomalies/statistics"
        )
    finally:
        app.dependency_overrides.clear()

    assert validation_status == 400
    assert validation_body["code"] == "VALIDATION_ERROR"
    assert persistence_status == 500
    assert persistence_body["code"] == "PERSISTENCE_ERROR"


def test_router_has_no_repository_orm_or_calculator_imports() -> None:
    from pathlib import Path

    source = (Path(__file__).parents[1] / "routers" / "anomaly.py").read_text(
        encoding="utf-8"
    )
    assert "repositories" not in source
    assert "from models" not in source
    assert "anomaly_detection" not in source
    assert ".commit(" not in source
    assert ".rollback(" not in source
