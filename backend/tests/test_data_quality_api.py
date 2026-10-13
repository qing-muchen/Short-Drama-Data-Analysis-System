"""Data-quality API schema, authorization, delegation, and error tests."""

import asyncio
from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from httpx import ASGITransport, AsyncClient

from auth.dependencies import get_current_user
from main import app
from routers.dependencies import get_data_quality_service
from services.exceptions import PersistenceException, ValidationException

SCORE_DATE = date(2026, 9, 16)
ANALYSIS_AS_OF = datetime(2026, 9, 16, 8, 30)
RULE_SET_HASH = "a" * 64


def _identity(role: str = "ADMINISTRATOR") -> SimpleNamespace:
    return SimpleNamespace(user_id=7, role_code=role, status="ACTIVE")


def _rule() -> SimpleNamespace:
    return SimpleNamespace(
        quality_rule_id=11,
        rule_code="DQ_COMPLETENESS_REQUIRED",
        rule_version="1.0",
        rule_name="Required drama fields",
        dimension="COMPLETENESS",
        target_entity_type="DRAMA",
        evaluator_key="required_field",
        scoring_method="PASS_RATE",
        weight=Decimal("1.000000"),
        severity="ERROR",
        configuration={"fields": ["drama_name"]},
        status="ACTIVE",
        valid_from=ANALYSIS_AS_OF,
        valid_to=None,
        description="Checks required fields",
    )


def _rule_result() -> SimpleNamespace:
    return SimpleNamespace(
        quality_rule_result_id=21,
        quality_rule_id=11,
        rule=_rule(),
        result_status="APPLIED",
        applicable_count=10,
        passed_count=9,
        failed_count=1,
        rule_score=Decimal("90.00"),
        not_applicable_reason=None,
        evidence_summary="10 records evaluated",
        created_at=ANALYSIS_AS_OF,
    )


def _score(score_id: int = 31, *, score_date: date = SCORE_DATE) -> SimpleNamespace:
    return SimpleNamespace(
        quality_score_id=score_id,
        score_date=score_date,
        score_scope_type="ALL",
        score_scope_id=0,
        analysis_as_of=ANALYSIS_AS_OF,
        completeness_score=Decimal("90.00"),
        accuracy_score=Decimal("88.00"),
        consistency_score=Decimal("86.00"),
        timeliness_score=Decimal("84.00"),
        total_score=Decimal("87.30"),
        quality_grade="A",
        algorithm_version="Quality Score V1.0",
        rule_set_version="DQ Rules 1.0",
        rule_set_hash=RULE_SET_HASH,
        evaluated_entity_count=10,
        open_issue_count=1,
        source_watermark={"snapshot_id": 100},
        created_at=ANALYSIS_AS_OF,
        updated_at=ANALYSIS_AS_OF,
        rule_results=[_rule_result()],
    )


class FakeDataQualityService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.current_score: Any | None = _score()
        self.history: list[Any] = [_score()]

    def calculate_quality_score(self, *args: Any, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(("calculate_quality_score", args, kwargs))
        return SimpleNamespace(
            quality_score_id=31,
            score_date=args[0],
            analysis_as_of=ANALYSIS_AS_OF,
            algorithm_version=kwargs.get("algorithm_version", "Quality Score V2.0"),
            rule_set_version="DQ Rules 1.0",
            rule_set_hash=RULE_SET_HASH,
            score_scope_type="ALL",
            score_scope_id=0,
            rule_count=4,
            applied_rule_count=3,
            not_applicable_rule_count=1,
            evaluated_entity_count=10,
            total_score=Decimal("87.30"),
            quality_grade="A",
        )

    def get_current_quality_score(self, **kwargs: Any) -> Any | None:
        self.calls.append(("get_current_quality_score", (), kwargs))
        return self.current_score

    def get_quality_history(self, **kwargs: Any) -> list[Any]:
        self.calls.append(("get_quality_history", (), kwargs))
        return self.history

    def get_current_quality_rules(self) -> SimpleNamespace:
        self.calls.append(("get_current_quality_rules", (), {}))
        rules = () if self.current_score is None else (_rule(),)
        return SimpleNamespace(
            rule_set_version="DQ Rules 1.0",
            rule_set_hash=RULE_SET_HASH if rules else None,
            rules=rules,
        )


def _request(method: str, path: str, **kwargs: Any) -> tuple[int, Any]:
    async def perform() -> tuple[int, Any]:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.request(method, path, **kwargs)
            return response.status_code, response.json()

    return asyncio.run(perform())


def _override(
    service: FakeDataQualityService,
    *,
    role: str = "ADMINISTRATOR",
) -> None:
    app.dependency_overrides[get_data_quality_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: _identity(role)


def test_dependency_composes_all_repositories_with_one_session() -> None:
    session = object()

    service = get_data_quality_service(session)  # type: ignore[arg-type]

    assert service._session is session
    assert service.rules.session is session
    assert service.rule_results.session is session
    assert service.scores.session is session
    assert service.operation_logs.session is session


def test_openapi_registers_data_quality_paths_with_jwt_and_error_models() -> None:
    schema = app.openapi()
    paths = schema["paths"]

    expected = (
        ("/api/v1/data-quality/calculate", "post"),
        ("/api/v1/data-quality/score", "get"),
        ("/api/v1/data-quality/history", "get"),
        ("/api/v1/data-quality/rules", "get"),
    )
    for path, method in expected:
        assert set(paths[path]) == {method}
        operation = paths[path][method]
        assert operation["security"] == [{"JWTBearer": []}]
        assert operation["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        error_schema = operation["responses"]["500"]["content"][
            "application/json"
        ]["schema"]
        assert error_schema["$ref"].endswith("/ErrorResponse")


def test_admin_calculate_delegates_only_allowed_request_fields() -> None:
    service = FakeDataQualityService()
    _override(service)
    try:
        status_code, body = _request(
            "POST",
            "/api/v1/data-quality/calculate",
            json={"score_date": SCORE_DATE.isoformat()},
        )
    finally:
        app.dependency_overrides.clear()

    assert status_code == 200
    assert service.calls == [
        (
            "calculate_quality_score",
            (SCORE_DATE,),
            {
                "administrator_id": 7,
                "algorithm_version": "Quality Score V2.0",
            },
        )
    ]
    assert body["message"] == "success"
    assert body["data"]["score_scope_type"] == "ALL"
    assert body["data"]["score_scope_id"] == 0
    assert body["data"]["total_score"] == 87.3


def test_anonymous_is_401_and_user_calculation_is_403() -> None:
    service = FakeDataQualityService()
    app.dependency_overrides[get_data_quality_service] = lambda: service
    try:
        anonymous_status, anonymous_body = _request(
            "POST",
            "/api/v1/data-quality/calculate",
            json={"score_date": SCORE_DATE.isoformat()},
        )
        app.dependency_overrides[get_current_user] = lambda: _identity("USER")
        user_status, user_body = _request(
            "POST",
            "/api/v1/data-quality/calculate",
            json={"score_date": SCORE_DATE.isoformat()},
        )
    finally:
        app.dependency_overrides.clear()

    assert anonymous_status == 401
    assert anonymous_body["code"] == "AUTHENTICATION_FAILED"
    assert user_status == 403
    assert user_body["code"] == "FORBIDDEN"
    assert service.calls == []


def test_user_reads_current_score_with_rule_results() -> None:
    service = FakeDataQualityService()
    _override(service, role="USER")
    try:
        status_code, body = _request("GET", "/api/v1/data-quality/score")
    finally:
        app.dependency_overrides.clear()

    assert status_code == 200
    assert service.calls == [
        (
            "get_current_quality_score",
            (),
            {"algorithm_version": "Quality Score V2.0"},
        )
    ]
    data = body["data"]
    assert data["quality_score_id"] == 31
    assert data["quality_grade"] == "A"
    assert data["rule_results"][0]["rule_code"] == "DQ_COMPLETENESS_REQUIRED"
    assert data["rule_results"][0]["failed_count"] == 1


def test_user_reads_filtered_history_and_empty_history() -> None:
    service = FakeDataQualityService()
    _override(service, role="USER")
    try:
        status_code, body = _request(
            "GET",
            "/api/v1/data-quality/history"
            "?start_date=2026-09-01&end_date=2026-09-16&limit=30",
        )
        service.history = []
        empty_status, empty_body = _request(
            "GET",
            "/api/v1/data-quality/history",
        )
    finally:
        app.dependency_overrides.clear()

    assert status_code == 200
    assert service.calls[0] == (
        "get_quality_history",
        (),
        {
            "start_date": date(2026, 9, 1),
            "end_date": SCORE_DATE,
            "limit": 30,
            "algorithm_version": "Quality Score V2.0",
        },
    )
    assert body["data"]["total"] == 1
    assert body["data"]["items"][0]["total_score"] == 87.3
    assert empty_status == 200
    assert empty_body["data"] == {"total": 0, "items": []}


def test_user_reads_rules_from_current_persisted_rule_set() -> None:
    service = FakeDataQualityService()
    _override(service, role="USER")
    try:
        status_code, body = _request("GET", "/api/v1/data-quality/rules")
        service.current_score = None
        empty_status, empty_body = _request(
            "GET",
            "/api/v1/data-quality/rules",
        )
    finally:
        app.dependency_overrides.clear()

    assert status_code == 200
    data = body["data"]
    assert data["rule_set_version"] == "DQ Rules 1.0"
    assert data["rule_set_hash"] == RULE_SET_HASH
    assert data["total"] == 1
    assert data["items"][0]["dimension"] == "COMPLETENESS"
    assert empty_status == 200
    assert empty_body["data"] == {
        "rule_set_version": "DQ Rules 1.0",
        "rule_set_hash": None,
        "total": 0,
        "items": [],
    }


def test_missing_current_score_returns_404_error_response() -> None:
    service = FakeDataQualityService()
    service.current_score = None
    _override(service, role="USER")
    try:
        status_code, body = _request("GET", "/api/v1/data-quality/score")
    finally:
        app.dependency_overrides.clear()

    assert status_code == 404
    assert body == {
        "code": "NOT_FOUND",
        "message": "Data quality score was not found",
        "details": None,
    }


def test_request_and_query_validation_reject_client_controlled_context() -> None:
    service = FakeDataQualityService()
    _override(service)
    try:
        responses = (
            _request(
                "POST",
                "/api/v1/data-quality/calculate",
                json={
                    "score_date": SCORE_DATE.isoformat(),
                    "rule_set_version": "client-controlled",
                    "scope_type": "TAG",
                    "scope_id": 1,
                },
            ),
            _request("GET", "/api/v1/data-quality/history?limit=0"),
            _request("GET", "/api/v1/data-quality/history?limit=366"),
            _request("GET", "/api/v1/data-quality/history?start_date=invalid"),
        )
    finally:
        app.dependency_overrides.clear()

    assert all(status == 422 for status, _ in responses)
    assert all(body["code"] == "REQUEST_VALIDATION_ERROR" for _, body in responses)
    assert service.calls == []


def test_service_errors_use_existing_global_error_mapping() -> None:
    class FailedDataQualityService(FakeDataQualityService):
        def calculate_quality_score(self, *args: Any, **kwargs: Any) -> Any:
            raise ValidationException("Quality score date cannot be in the future")

        def get_quality_history(self, **kwargs: Any) -> list[Any]:
            raise PersistenceException()

    service = FailedDataQualityService()
    _override(service)
    try:
        validation_status, validation_body = _request(
            "POST",
            "/api/v1/data-quality/calculate",
            json={"score_date": SCORE_DATE.isoformat()},
        )
        persistence_status, persistence_body = _request(
            "GET",
            "/api/v1/data-quality/history",
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
