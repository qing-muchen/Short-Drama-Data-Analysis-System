"""Prediction API schema, authorization, delegation, and error tests."""

import asyncio
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from httpx import ASGITransport, AsyncClient

from auth.dependencies import get_current_user
from main import app
from routers.dependencies import get_prediction_service
from services.exceptions import PersistenceException, ValidationException

DRAMA_ID = 7
ANALYSIS_AS_OF = datetime(2026, 9, 16, 12, 0)


def _identity(role: str = "ADMINISTRATOR") -> SimpleNamespace:
    return SimpleNamespace(user_id=3, role_code=role, status="ACTIVE")


def _prediction(prediction_id: int = 11) -> SimpleNamespace:
    return SimpleNamespace(
        prediction_id=prediction_id,
        drama_id=DRAMA_ID,
        metric_type="PLAY_COUNT",
        algorithm_version="Moving Average V1.0",
        analysis_as_of=ANALYSIS_AS_OF,
        prediction_date=date(2026, 9, 16),
        target_date=date(2026, 9, 17),
        predicted_value=Decimal("190.00"),
        created_at=ANALYSIS_AS_OF,
    )


class FakePredictionService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.latest: Any | None = _prediction()
        self.history: list[Any] = [_prediction(), _prediction(12)]
        self.calculation = SimpleNamespace(prediction=_prediction())

    def calculate_prediction(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(("calculate_prediction", args, kwargs))
        return self.calculation

    def get_latest_prediction(self, *args: Any, **kwargs: Any) -> Any | None:
        self.calls.append(("get_latest_prediction", args, kwargs))
        return self.latest

    def get_prediction_history(self, *args: Any, **kwargs: Any) -> list[Any]:
        self.calls.append(("get_prediction_history", args, kwargs))
        return self.history


def _request(method: str, path: str, **kwargs: Any) -> tuple[int, Any]:
    async def perform() -> tuple[int, Any]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.request(method, path, **kwargs)
            return response.status_code, response.json()

    return asyncio.run(perform())


def _override(service: FakePredictionService, *, role: str = "ADMINISTRATOR") -> None:
    app.dependency_overrides[get_prediction_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: _identity(role)


def test_openapi_registers_prediction_paths_with_jwt_bearer() -> None:
    paths = app.openapi()["paths"]
    assert set(paths["/api/v1/predictions/calculate"]) == {"post"}
    assert set(paths["/api/v1/predictions/{drama_id}/history"]) == {"get"}
    assert set(paths["/api/v1/predictions/{drama_id}"]) == {"get"}
    for path, method in (
        ("/api/v1/predictions/calculate", "post"),
        ("/api/v1/predictions/{drama_id}/history", "get"),
        ("/api/v1/predictions/{drama_id}", "get"),
    ):
        operation = paths[path][method]
        assert operation["security"] == [{"JWTBearer": []}]
        assert operation["responses"]["500"]["content"][
            "application/json"
        ]["schema"]["$ref"].endswith("/ErrorResponse")


def test_admin_calculate_delegates_drama_and_analysis_as_of() -> None:
    service = FakePredictionService()
    _override(service)
    try:
        status, body = _request(
            "POST",
            "/api/v1/predictions/calculate",
            json={
                "drama_id": DRAMA_ID,
                "analysis_as_of": ANALYSIS_AS_OF.isoformat(),
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert status == 200
    assert service.calls == [
        (
            "calculate_prediction",
            (DRAMA_ID,),
            {"analysis_as_of": ANALYSIS_AS_OF, "administrator_id": 3},
        )
    ]
    assert body["message"] == "success"
    assert body["data"] == {
        "prediction_id": 11,
        "drama_id": DRAMA_ID,
        "metric_type": "PLAY_COUNT",
        "algorithm_version": "Moving Average V1.0",
        "analysis_as_of": ANALYSIS_AS_OF.isoformat(),
        "target_date": "2026-09-17",
        "predicted_value": 190.0,
        "created_at": ANALYSIS_AS_OF.isoformat(),
    }


def test_anonymous_is_401_and_user_calculation_is_403() -> None:
    service = FakePredictionService()
    app.dependency_overrides[get_prediction_service] = lambda: service
    try:
        anonymous_status, anonymous_body = _request(
            "POST",
            "/api/v1/predictions/calculate",
            json={"drama_id": DRAMA_ID},
        )
        app.dependency_overrides[get_current_user] = lambda: _identity("USER")
        user_status, user_body = _request(
            "POST",
            "/api/v1/predictions/calculate",
            json={"drama_id": DRAMA_ID},
        )
    finally:
        app.dependency_overrides.clear()

    assert anonymous_status == 401
    assert anonymous_body["code"] == "AUTHENTICATION_FAILED"
    assert user_status == 403
    assert user_body["code"] == "FORBIDDEN"
    assert service.calls == []


def test_authenticated_user_reads_latest_prediction_and_history() -> None:
    service = FakePredictionService()
    _override(service, role="USER")
    try:
        latest_status, latest_body = _request(
            "GET", f"/api/v1/predictions/{DRAMA_ID}"
        )
        history_status, history_body = _request(
            "GET", f"/api/v1/predictions/{DRAMA_ID}/history?limit=12"
        )
    finally:
        app.dependency_overrides.clear()

    assert latest_status == 200
    assert latest_body["data"]["predicted_value"] == 190.0
    assert history_status == 200
    assert history_body["data"]["drama_id"] == DRAMA_ID
    assert len(history_body["data"]["items"]) == 2
    assert service.calls == [
        ("get_latest_prediction", (DRAMA_ID,), {}),
        ("get_prediction_history", (DRAMA_ID,), {"limit": 12}),
    ]


def test_missing_prediction_returns_404() -> None:
    service = FakePredictionService()
    service.latest = None
    _override(service, role="USER")
    try:
        status, body = _request("GET", f"/api/v1/predictions/{DRAMA_ID}")
    finally:
        app.dependency_overrides.clear()

    assert status == 404
    assert body == {
        "code": "NOT_FOUND",
        "message": "Prediction was not found",
        "details": {"drama_id": DRAMA_ID},
    }


def test_validation_rejects_invalid_ids_limits_and_client_algorithm_fields() -> None:
    service = FakePredictionService()
    _override(service)
    try:
        responses = (
            _request(
                "POST",
                "/api/v1/predictions/calculate",
                json={
                    "drama_id": 0,
                    "algorithm_version": "client-controlled",
                },
            ),
            _request("GET", "/api/v1/predictions/0"),
            _request("GET", f"/api/v1/predictions/{DRAMA_ID}/history?limit=101"),
        )
    finally:
        app.dependency_overrides.clear()

    assert all(status == 422 for status, _ in responses)
    assert all(body["code"] == "REQUEST_VALIDATION_ERROR" for _, body in responses)
    assert service.calls == []


def test_service_skip_and_persistence_errors_use_global_mapping() -> None:
    class FailedPredictionService(FakePredictionService):
        def calculate_prediction(self, *args: Any, **kwargs: Any) -> Any:
            raise ValidationException(
                "Prediction history is insufficient",
                details={"reason": "INSUFFICIENT_HISTORY"},
            )

        def get_latest_prediction(self, *args: Any, **kwargs: Any) -> Any | None:
            raise PersistenceException()

    service = FailedPredictionService()
    _override(service)
    try:
        validation_status, validation_body = _request(
            "POST",
            "/api/v1/predictions/calculate",
            json={"drama_id": DRAMA_ID},
        )
        persistence_status, persistence_body = _request(
            "GET", f"/api/v1/predictions/{DRAMA_ID}"
        )
    finally:
        app.dependency_overrides.clear()

    assert validation_status == 400
    assert validation_body["code"] == "VALIDATION_ERROR"
    assert persistence_status == 500
    assert persistence_body["code"] == "PERSISTENCE_ERROR"


def test_skipped_service_result_maps_to_validation_error() -> None:
    service = FakePredictionService()
    service.calculation = SimpleNamespace(
        prediction=None,
        skipped_reason="NO_HISTORY",
    )
    _override(service)
    try:
        status, body = _request(
            "POST",
            "/api/v1/predictions/calculate",
            json={"drama_id": DRAMA_ID},
        )
    finally:
        app.dependency_overrides.clear()

    assert status == 400
    assert body["code"] == "VALIDATION_ERROR"
    assert body["details"] == {"reason": "NO_HISTORY"}
