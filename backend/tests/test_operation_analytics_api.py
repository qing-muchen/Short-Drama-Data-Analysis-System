"""API boundary tests for Phase 8 operation analytics."""

from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from auth.dependencies import require_user
from main import app
from routers.dependencies import get_operation_analytics_service
from services.operation_analytics.contracts import (
    AnalysisAvailability,
    AnalysisWindow,
    AvailabilityReason,
    AvailabilityStatus,
    BENCHMARK_VERSION,
    BenchmarkMemberResult,
    BenchmarkMetric,
    BenchmarkMetricType,
    BenchmarkResult,
    ComparisonScope,
    LIFECYCLE_RULE_VERSION,
    LifecycleResult,
    LifecycleStage,
    MetricChange,
    MetricDirection,
    OperationEffectivenessResult,
    OperationMetricType,
)
from services.operation_analytics.service import OperationEffectivenessResultPage


AS_OF = datetime(2026, 9, 20, tzinfo=timezone.utc)
WINDOW_7 = AnalysisWindow(date(2026, 9, 1), date(2026, 9, 7), 7)
WINDOW_30 = AnalysisWindow(date(2026, 8, 21), date(2026, 9, 19), 30)
AVAILABLE = AnalysisAvailability(AvailabilityStatus.AVAILABLE)


class FakeOperationAnalyticsService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def get_operation_effectiveness(self, **kwargs):
        self.calls.append(("effectiveness", kwargs))
        item = OperationEffectivenessResult(
            action_id=9,
            drama_id=7,
            before_window=WINDOW_7,
            after_window=AnalysisWindow(date(2026, 9, 9), date(2026, 9, 15), 7),
            metric_changes=(
                MetricChange(
                    metric_type=OperationMetricType.PLAY_COUNT,
                    before_value=100,
                    after_value=120,
                    absolute_change=20,
                    relative_change=Decimal("0.2"),
                    direction=MetricDirection.INCREASED,
                    unit="count",
                    availability=AVAILABLE,
                ),
            ),
            availability=AnalysisAvailability(
                AvailabilityStatus.PARTIAL,
                (AvailabilityReason.OVERLAPPING_ACTIONS,),
            ),
            anchor_time=AS_OF,
            overlapping_action_ids=(10,),
            analysis_revision="effect-revision",
            analysis_as_of=kwargs.get("analysis_as_of") or AS_OF,
        )
        return OperationEffectivenessResultPage(
            page=kwargs["page"],
            page_size=kwargs["page_size"],
            total=1,
            items=(item,),
            availability=item.availability,
            analysis_as_of=item.analysis_as_of,
        )

    def get_lifecycle(self, **kwargs):
        self.calls.append(("lifecycle", kwargs))
        return LifecycleResult(
            drama_id=kwargs["drama_id"],
            lifecycle_stage=LifecycleStage.GROWTH,
            rule_version=LIFECYCLE_RULE_VERSION,
            evaluated_as_of=kwargs.get("analysis_as_of") or AS_OF,
            availability=AVAILABLE,
            analysis_revision="lifecycle-revision",
        )

    def get_benchmark(self, **kwargs):
        self.calls.append(("benchmark", kwargs))
        metric = BenchmarkMetric(
            metric_type=BenchmarkMetricType.PLAY_INCREMENT_TOTAL,
            value=Decimal("30"),
            group_median=Decimal("25"),
            unit="count",
            availability=AVAILABLE,
        )
        members = tuple(
            BenchmarkMemberResult(drama_id, (metric,), AVAILABLE)
            for drama_id in kwargs["drama_ids"]
        )
        return BenchmarkResult(
            target_drama_id=None,
            comparison_scope=ComparisonScope(
                tuple(kwargs["drama_ids"]), kwargs["platform_id"]
            ),
            window=WINDOW_30,
            metrics=members,
            availability=AVAILABLE,
            benchmark_version=BENCHMARK_VERSION,
            lifecycle_rule_version=LIFECYCLE_RULE_VERSION,
            analysis_revision="benchmark-revision",
            analysis_as_of=kwargs.get("analysis_as_of") or AS_OF,
        )


@contextmanager
def api_client(*, role: str | None = "USER"):
    fake = FakeOperationAnalyticsService()
    app.dependency_overrides[get_operation_analytics_service] = lambda: fake
    if role is not None:
        app.dependency_overrides[require_user] = lambda: SimpleNamespace(
            user_id=1,
            role_code=role,
        )
    try:
        yield TestClient(app), fake
    finally:
        app.dependency_overrides.pop(get_operation_analytics_service, None)
        app.dependency_overrides.pop(require_user, None)


def test_routes_are_registered_as_get_only() -> None:
    expected = {
        "/api/v1/operations/effectiveness",
        "/api/v1/dramas/{drama_id}/lifecycle",
        "/api/v1/dramas/benchmark",
    }
    schema = app.openapi()
    paths = set(schema["paths"])
    assert expected <= paths
    for path in expected:
        methods = set(schema["paths"][path])
        assert methods == {"get"}


def test_anonymous_request_returns_401() -> None:
    with api_client(role=None) as (client, _fake):
        response = client.get("/api/v1/dramas/7/lifecycle")
    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_FAILED"


def test_user_and_administrator_can_query() -> None:
    for role in ("USER", "ADMINISTRATOR"):
        with api_client(role=role) as (client, _fake):
            response = client.get("/api/v1/dramas/7/lifecycle")
        assert response.status_code == 200
        assert response.json()["data"]["lifecycle_stage"] == "GROWTH"


def test_effectiveness_schema_and_availability_are_preserved() -> None:
    with api_client() as (client, _fake):
        response = client.get(
            "/api/v1/operations/effectiveness",
            params={"action_id": 9, "drama_id": 7, "page": 2, "page_size": 5},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "success"
    assert body["data"]["page"] == 2
    assert body["data"]["items"][0]["action_id"] == 9
    assert body["data"]["availability"] == {
        "status": "PARTIAL",
        "reasons": ["OVERLAPPING_ACTIONS"],
    }
    assert "success" not in body["data"]["items"][0]
    assert "causal_result" not in body["data"]["items"][0]
    assert "recommendation" not in body["data"]["items"][0]


def test_analysis_as_of_and_filters_are_passed_to_service() -> None:
    with api_client() as (client, fake):
        response = client.get(
            "/api/v1/operations/effectiveness",
            params={
                "action_id": 9,
                "drama_id": 7,
                "analysis_as_of": AS_OF.isoformat(),
                "page": 3,
                "page_size": 10,
            },
        )
    assert response.status_code == 200
    name, kwargs = fake.calls[0]
    assert name == "effectiveness"
    assert kwargs == {
        "action_id": 9,
        "drama_id": 7,
        "analysis_as_of": AS_OF,
        "page": 3,
        "page_size": 10,
    }


def test_lifecycle_path_and_as_of_are_passed_to_service() -> None:
    with api_client() as (client, fake):
        response = client.get(
            "/api/v1/dramas/8/lifecycle",
            params={"analysis_as_of": AS_OF.isoformat()},
        )
    assert response.status_code == 200
    assert fake.calls == [
        ("lifecycle", {"drama_id": 8, "analysis_as_of": AS_OF})
    ]


def test_benchmark_static_route_and_parameters() -> None:
    with api_client() as (client, fake):
        response = client.get(
            "/api/v1/dramas/benchmark",
            params=[
                ("drama_ids", "7"),
                ("drama_ids", "8"),
                ("platform_id", "3"),
                ("analysis_as_of", AS_OF.isoformat()),
            ],
        )
    assert response.status_code == 200
    assert response.json()["data"]["comparison_scope"]["drama_ids"] == [7, 8]
    assert fake.calls == [
        (
            "benchmark",
            {
                "drama_ids": [7, 8],
                "platform_id": 3,
                "analysis_as_of": AS_OF,
            },
        )
    ]


def test_invalid_query_parameters_return_unified_422() -> None:
    with api_client() as (client, _fake):
        response = client.get(
            "/api/v1/dramas/benchmark",
            params={"drama_ids": 7, "platform_id": 0},
        )
    assert response.status_code == 422
    assert response.json()["code"] == "REQUEST_VALIDATION_ERROR"


def test_openapi_contains_security_parameters_and_response_models() -> None:
    schema = app.openapi()
    assert "JWTBearer" in schema["components"]["securitySchemes"]
    for path in (
        "/api/v1/operations/effectiveness",
        "/api/v1/dramas/{drama_id}/lifecycle",
        "/api/v1/dramas/benchmark",
    ):
        operation = schema["paths"][path]["get"]
        assert operation["security"]
        assert "200" in operation["responses"]


def test_dependency_override_avoids_database_access() -> None:
    with api_client() as (client, fake):
        response = client.get("/api/v1/dramas/11/lifecycle")
    assert response.status_code == 200
    assert fake.calls[0][1]["drama_id"] == 11


def test_router_source_respects_layer_boundary() -> None:
    source = (
        Path(__file__).parents[1] / "routers" / "operation_analytics.py"
    ).read_text(encoding="utf-8")
    lowered = source.lower()
    assert "sqlalchemy" not in lowered
    assert "repositories." not in lowered
    assert "models." not in lowered
    assert "providers" not in lowered
    assert "rules" not in lowered
    assert "session" not in lowered
