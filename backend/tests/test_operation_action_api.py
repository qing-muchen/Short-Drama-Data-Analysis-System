"""HTTP boundary tests for the Phase 5 operation-action API."""

import asyncio
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from httpx import ASGITransport, AsyncClient

from auth.dependencies import get_current_user
from main import app
from repositories.base import Page
from routers.dependencies import get_operation_action_service


NOW = datetime(2026, 9, 21)


def _user(role: str) -> SimpleNamespace:
    return SimpleNamespace(user_id=7, role_code=role, status="ACTIVE")


def _action() -> SimpleNamespace:
    user = SimpleNamespace(user_id=7, username="admin", display_name="Admin", role_code="ADMINISTRATOR")
    return SimpleNamespace(action_id=1, drama_id=None, title="Review anomaly", description=None,
                           priority="HIGH", status="OPEN", assignee=None, created_by=user,
                           due_date=None, created_at=NOW, updated_at=NOW, sources=[], history=[])


class FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.entity = _action()

    def create_action(self, **kwargs: Any) -> Any:
        self.calls.append(("create_action", (), kwargs)); return self.entity

    def list_actions(self, **kwargs: Any) -> Page[Any]:
        self.calls.append(("list_actions", (), kwargs)); return Page(1, 20, 1, [self.entity])

    def get_action(self, action_id: int) -> Any:
        self.calls.append(("get_action", (action_id,), {})); return self.entity

    def get_statistics(self) -> dict[str, int]:
        self.calls.append(("get_statistics", (), {})); return {"total": 1, "OPEN": 1, "IN_PROGRESS": 0, "COMPLETED": 0, "CANCELLED": 0}

    def update_status(self, **kwargs: Any) -> Any:
        self.calls.append(("update_status", (), kwargs)); return self.entity

    def assign_action(self, **kwargs: Any) -> Any:
        self.calls.append(("assign_action", (), kwargs)); return self.entity

    def add_comment(self, **kwargs: Any) -> Any:
        self.calls.append(("add_comment", (), kwargs)); return SimpleNamespace(history_id=2, event_type="COMMENT",
            old_status=None, new_status=None, operator_user_id=7, comment=kwargs["comment"], created_at=NOW)


def _request(method: str, path: str, **kwargs: Any) -> tuple[int, Any]:
    async def run() -> tuple[int, Any]:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.request(method, path, **kwargs)
            return response.status_code, response.json()
    return asyncio.run(run())


def _override(service: FakeService, role: str = "ADMINISTRATOR") -> None:
    app.dependency_overrides[get_operation_action_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: _user(role)


def test_openapi_registers_operation_action_paths() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/operation-actions/statistics" in paths
    assert "/api/v1/operation-actions/{action_id}" in paths
    assert paths["/api/v1/operation-actions"]["post"]["security"] == [{"JWTBearer": []}]


def test_admin_create_passes_operator_and_source() -> None:
    service = FakeService(); _override(service)
    try:
        status, body = _request("POST", "/api/v1/operation-actions", json={
            "title": "Review anomaly", "priority": "HIGH",
            "source": {"source_type": "MANUAL", "source_evidence_summary": "Operator note"},
        })
    finally:
        app.dependency_overrides.clear()
    assert status == 200
    assert service.calls[0][0] == "create_action"
    assert service.calls[0][2]["operator_user_id"] == 7
    assert service.calls[0][2]["operator_role"] == "ADMINISTRATOR"
    assert body["data"]["action_id"] == 1


def test_user_can_list_comment_but_cannot_create_or_update_status() -> None:
    service = FakeService(); _override(service, "USER")
    try:
        create_status, _ = _request("POST", "/api/v1/operation-actions", json={"title": "x"})
        list_status, _ = _request("GET", "/api/v1/operation-actions?page=2&page_size=10")
        comment_status, _ = _request("POST", "/api/v1/operation-actions/1/comments", json={"comment": "working"})
        update_status, _ = _request("PATCH", "/api/v1/operation-actions/1/status", json={"new_status": "IN_PROGRESS"})
    finally:
        app.dependency_overrides.clear()
    assert create_status == 403
    assert list_status == 200
    assert comment_status == 200
    assert update_status == 403
    assert service.calls[0][0] == "list_actions"
    assert service.calls[0][2]["page"] == 2


def test_validation_rejects_invalid_status_and_page_size() -> None:
    service = FakeService(); _override(service)
    try:
        invalid_status, _ = _request("PATCH", "/api/v1/operation-actions/1/status", json={"new_status": "BAD"})
        invalid_page, _ = _request("GET", "/api/v1/operation-actions?page_size=101")
    finally:
        app.dependency_overrides.clear()
    assert invalid_status == 422
    assert invalid_page == 422
