"""API boundary tests for the Phase 9 data governance read model."""

from __future__ import annotations

import ast
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from auth.dependencies import require_user
from main import app
from routers.dependencies import get_data_governance_service
from services.data_governance.contracts import (
    AvailabilityReason,
    AvailabilityStatus,
    CompletenessResult,
    ConsistencyResult,
    DataGovernanceResponse,
    DataQualityAvailability,
    EvidenceItem,
    FreshnessResult,
    GovernanceScope,
    QualityIssueType,
    QualityStatus,
)


AS_OF = datetime(2026, 9, 23, 8, 0, tzinfo=timezone.utc)
PATHS = (
    "/api/v1/data-quality/overview",
    "/api/v1/data-quality/freshness",
    "/api/v1/data-quality/completeness",
    "/api/v1/data-quality/consistency",
)


def _availability(status: AvailabilityStatus) -> DataQualityAvailability:
    reasons = {
        AvailabilityStatus.AVAILABLE: (),
        AvailabilityStatus.PARTIAL: (AvailabilityReason.MISSING_SOURCE,),
        AvailabilityStatus.INSUFFICIENT: (AvailabilityReason.INSUFFICIENT_HISTORY,),
        AvailabilityStatus.NOT_AVAILABLE: (AvailabilityReason.EVALUATION_FAILED,),
    }
    return DataQualityAvailability(status, reasons[status])


def _evidence(issue_type: QualityIssueType) -> EvidenceItem:
    return EvidenceItem(
        issue_type=issue_type,
        check_code=f"{issue_type.value}_CHECK",
        entity_type=GovernanceScope.SYSTEM.value,
        entity_id=None,
        observed_value=("visible", 1),
        expected_condition="the governance input is available",
        source_type="SYSTEM_READ_MODEL",
        source_reference_ids=(1,),
        message=f"{issue_type.value} evidence.",
    )


class FakeDataGovernanceService:
    def __init__(
        self,
        availability_status: AvailabilityStatus = AvailabilityStatus.AVAILABLE,
    ) -> None:
        self.availability_status = availability_status
        self.calls: list[tuple[str, datetime | None]] = []

    def _results(self, as_of: datetime):
        availability = _availability(self.availability_status)
        healthy = self.availability_status is AvailabilityStatus.AVAILABLE
        quality_status = QualityStatus.HEALTHY if healthy else QualityStatus.NOT_AVAILABLE
        freshness_evidence = () if healthy else (_evidence(QualityIssueType.FRESHNESS),)
        completeness_evidence = () if healthy else (
            _evidence(QualityIssueType.COMPLETENESS),
        )
        consistency_evidence = () if healthy else (
            _evidence(QualityIssueType.CONSISTENCY),
        )
        freshness = FreshnessResult(
            status=quality_status,
            availability=availability,
            delay_seconds=120 if healthy else None,
            evidence=freshness_evidence,
            analysis_as_of=as_of,
            summary="Freshness API fixture.",
        )
        completeness = CompletenessResult(
            status=quality_status,
            availability=availability,
            coverage_ratio=None,
            missing_items=(),
            evidence=completeness_evidence,
            analysis_as_of=as_of,
            summary="Completeness API fixture.",
        )
        consistency = ConsistencyResult(
            status=quality_status,
            availability=availability,
            issue_count=len(consistency_evidence),
            evidence=consistency_evidence,
            analysis_as_of=as_of,
            summary="Consistency API fixture.",
        )
        return freshness, completeness, consistency

    def get_overview(self, *, analysis_as_of: datetime | None = None):
        self.calls.append(("overview", analysis_as_of))
        as_of = analysis_as_of or AS_OF
        freshness, completeness, consistency = self._results(as_of)
        return DataGovernanceResponse(
            analysis_as_of=as_of,
            scope=GovernanceScope.SYSTEM,
            availability=_availability(self.availability_status),
            freshness=freshness,
            completeness=completeness,
            consistency=consistency,
        )

    def get_freshness(self, *, analysis_as_of: datetime | None = None):
        self.calls.append(("freshness", analysis_as_of))
        return self._results(analysis_as_of or AS_OF)[0]

    def get_completeness(self, *, analysis_as_of: datetime | None = None):
        self.calls.append(("completeness", analysis_as_of))
        return self._results(analysis_as_of or AS_OF)[1]

    def get_consistency(self, *, analysis_as_of: datetime | None = None):
        self.calls.append(("consistency", analysis_as_of))
        return self._results(analysis_as_of or AS_OF)[2]


@contextmanager
def api_client(
    *,
    role: str | None = "USER",
    availability_status: AvailabilityStatus = AvailabilityStatus.AVAILABLE,
):
    fake = FakeDataGovernanceService(availability_status)
    app.dependency_overrides[get_data_governance_service] = lambda: fake
    if role is not None:
        app.dependency_overrides[require_user] = lambda: SimpleNamespace(
            user_id=1,
            role_code=role,
        )
    try:
        yield TestClient(app), fake
    finally:
        app.dependency_overrides.pop(get_data_governance_service, None)
        app.dependency_overrides.pop(require_user, None)


def test_four_routes_are_registered_as_get_only() -> None:
    schema = app.openapi()
    assert set(PATHS) <= set(schema["paths"])
    for path in PATHS:
        assert set(schema["paths"][path]) == {"get"}


@pytest.mark.parametrize("path", PATHS)
def test_anonymous_requests_return_401(path: str) -> None:
    with api_client(role=None) as (client, _fake):
        response = client.get(path)

    assert response.status_code == 401
    assert response.json()["code"] == "AUTHENTICATION_FAILED"


@pytest.mark.parametrize("role", ("USER", "ADMINISTRATOR"))
def test_user_and_administrator_can_query_all_routes(role: str) -> None:
    with api_client(role=role) as (client, fake):
        responses = [client.get(path) for path in PATHS]

    assert all(response.status_code == 200 for response in responses)
    assert [name for name, _ in fake.calls] == [
        "overview",
        "freshness",
        "completeness",
        "consistency",
    ]


def test_overview_converts_service_dto_to_public_schema() -> None:
    with api_client() as (client, _fake):
        response = client.get(PATHS[0])

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["scope"] == "SYSTEM"
    assert data["analysis_as_of"] == "2026-09-23T08:00:00Z"
    assert data["availability"] == {
        "status": "AVAILABLE",
        "reasons": [],
        "message": None,
    }
    assert data["freshness"]["delay_seconds"] == 120
    assert data["freshness"]["rule_version"] == "Freshness Rules V1.0"
    assert data["rule_set_version"] == "Governance Rule Set V1.0"


@pytest.mark.parametrize(
    "status",
    (
        AvailabilityStatus.AVAILABLE,
        AvailabilityStatus.PARTIAL,
        AvailabilityStatus.INSUFFICIENT,
        AvailabilityStatus.NOT_AVAILABLE,
    ),
)
def test_availability_states_are_preserved(status: AvailabilityStatus) -> None:
    with api_client(availability_status=status) as (client, _fake):
        response = client.get(PATHS[0])

    assert response.status_code == 200
    assert response.json()["data"]["availability"]["status"] == status.value


def test_evidence_is_explicitly_mapped_without_exposing_contract_object() -> None:
    with api_client(availability_status=AvailabilityStatus.PARTIAL) as (client, _fake):
        response = client.get(PATHS[1])

    evidence = response.json()["data"]["evidence"][0]
    assert evidence["evidence_type"] == "FRESHNESS"
    assert evidence["source"] == "SYSTEM_READ_MODEL"
    assert evidence["metadata"]["check_code"] == "FRESHNESS_CHECK"
    assert evidence["metadata"]["observed_value"] == ["visible", 1]
    assert "issue_type" not in evidence


def test_analysis_as_of_and_evidence_paging_are_validated_and_forwarded() -> None:
    with api_client(availability_status=AvailabilityStatus.PARTIAL) as (client, fake):
        response = client.get(
            PATHS[1],
            params={
                "analysis_as_of": AS_OF.isoformat(),
                "page": 2,
                "page_size": 1,
            },
        )

    assert response.status_code == 200
    assert fake.calls == [("freshness", AS_OF)]
    assert response.json()["data"]["page"] == 2
    assert response.json()["data"]["page_size"] == 1
    assert response.json()["data"]["total"] == 1
    assert response.json()["data"]["evidence"] == []


@pytest.mark.parametrize(
    ("path", "params"),
    (
        (PATHS[0], {"analysis_as_of": "2026-09-23T08:00:00"}),
        (PATHS[1], {"page": 0}),
        (PATHS[2], {"page_size": 101}),
    ),
)
def test_invalid_query_parameters_return_unified_422(
    path: str,
    params: dict[str, object],
) -> None:
    with api_client() as (client, _fake):
        response = client.get(path, params=params)

    assert response.status_code == 422
    assert response.json()["code"] == "REQUEST_VALIDATION_ERROR"


def test_openapi_has_jwt_security_and_public_response_models() -> None:
    schema = app.openapi()
    assert "JWTBearer" in schema["components"]["securitySchemes"]
    for path in PATHS:
        operation = schema["paths"][path]["get"]
        assert operation["security"]
        assert "200" in operation["responses"]


def test_dependency_override_avoids_database_access() -> None:
    with api_client() as (client, fake):
        response = client.get(PATHS[3])

    assert response.status_code == 200
    assert fake.calls == [("consistency", None)]


def test_router_source_respects_layer_boundary() -> None:
    router_path = Path(__file__).parents[1] / "routers" / "data_governance.py"
    source = router_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    forbidden = ("sqlalchemy", "models", "repositories", "providers", "rules")
    assert not any(
        fragment in module
        for module in imported_modules
        for fragment in forbidden
    )
    lowered = source.lower()
    for forbidden_call in ("commit(", "rollback(", "flush(", "session.", "select("):
        assert forbidden_call not in lowered
