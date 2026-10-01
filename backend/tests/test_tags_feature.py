"""Tag CRUD, drama-tag editing/filtering, and Dashboard tag endpoint tests."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, create_autospec

from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from auth.dependencies import get_current_user
from main import app
from repositories.base import Page
from repositories.dashboard_repository import DashboardRepository
from repositories.drama_repository import DramaRepository
from repositories.tag_repository import TagRepository
from routers.dependencies import get_master_data_service
from services.drama_service import DramaService


def _session() -> Session:
    return create_autospec(Session, instance=True)


def _drama() -> SimpleNamespace:
    now = datetime.now(UTC).replace(tzinfo=None)
    return SimpleNamespace(
        drama_id=7,
        drama_code="DRM000007",
        drama_name="Tagged Drama",
        synopsis=None,
        episode_count=None,
        episode_duration_seconds=None,
        premiere_date=None,
        status="DRAFT",
        created_at=now,
        updated_at=now,
        tags=[],
        platforms=[],
    )


def test_drama_create_and_update_replace_active_tag_relations() -> None:
    session = _session()
    dramas = DramaRepository(session)
    tags = TagRepository(session)
    entity = _drama()
    dramas.get_by_drama_code = MagicMock(return_value=None)
    dramas.create = MagicMock(return_value=entity)
    dramas.get_by_id = MagicMock(return_value=entity)
    dramas.update = MagicMock(return_value=entity)
    dramas.replace_tags = MagicMock()
    tags.get_active_ids = MagicMock(return_value={1, 3, 5})
    service = DramaService(session, dramas, tags)

    created = service.create_drama(
        {"drama_name": "Tagged Drama", "tags": [1, 3, 3]}
    )
    updated = service.update_drama(7, {"tags": [3, 5]})

    assert created is entity and updated is entity
    assert "tags" not in dramas.create.call_args.args[0]
    assert dramas.replace_tags.call_args_list[0].args == (7, (1, 3))
    assert dramas.replace_tags.call_args_list[1].args == (7, (3, 5))
    assert session.commit.call_count == 2


def test_drama_repository_tag_filter_requires_every_selected_tag() -> None:
    session = _session()
    repository = DramaRepository(session)
    repository.paginate = MagicMock(return_value=Page(1, 20, 0, []))

    repository.list_page(page=1, page_size=20, tag_ids=(1, 3))

    statement = repository.paginate.call_args.args[0]
    sql = str(
        statement.compile(
            dialect=mysql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()
    assert "drama_tags.tag_id in (1, 3)" in sql
    assert "drama_tags.relation_status = 'active'" in sql
    assert "having count(distinct(drama_tags.tag_id)) = 2" in sql


def test_dashboard_tag_distribution_uses_one_aggregate_query() -> None:
    from repositories.dashboard_repository import DashboardRepository

    session = _session()
    session.execute.return_value.all.return_value = [("都市", 35, 100)]
    repository = DashboardRepository(session)

    result = repository.get_tag_distribution(10)

    assert result[0].tag_name == "都市"
    assert result[0].drama_count == 35
    session.execute.assert_called_once()
    session.scalar.assert_not_called()


class FakeTagService:
    def __init__(self) -> None:
        self.now = datetime.now(UTC).replace(tzinfo=None)

    def _tag(self, status: str = "ACTIVE") -> SimpleNamespace:
        return SimpleNamespace(
            tag_id=1,
            tag_name="都市",
            status=status,
            created_at=self.now,
            updated_at=self.now,
            drama_count=35,
        )

    def list_tags(self, **filters: Any) -> SimpleNamespace:
        return SimpleNamespace(
            page=filters["page"],
            page_size=filters["page_size"],
            total=1,
            items=[self._tag()],
        )

    def get_tag(self, tag_id: int) -> SimpleNamespace:
        return self._tag()

    def create_tag(self, values: dict[str, Any]) -> SimpleNamespace:
        return self._tag()

    def update_tag(self, tag_id: int, values: dict[str, Any]) -> SimpleNamespace:
        return self._tag()

    def deactivate_tag(self, tag_id: int) -> SimpleNamespace:
        return self._tag("INACTIVE")


def _request(method: str, path: str, **kwargs: Any) -> tuple[int, Any]:
    async def perform() -> tuple[int, Any]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.request(method, path, **kwargs)
            return response.status_code, response.json()

    return asyncio.run(perform())


def test_tag_crud_routes_include_associated_drama_count() -> None:
    service = FakeTagService()
    app.dependency_overrides[get_master_data_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        role_code="ADMINISTRATOR", status="ACTIVE"
    )
    try:
        listed = _request("GET", "/api/v1/tags?page=1&page_size=20")
        created = _request("POST", "/api/v1/tags", json={"tag_name": "都市"})
        updated = _request("PUT", "/api/v1/tags/1", json={"tag_name": "都市"})
        deleted = _request("DELETE", "/api/v1/tags/1")
    finally:
        app.dependency_overrides.clear()

    assert listed[0] == 200
    assert listed[1]["data"]["items"][0]["drama_count"] == 35
    assert created[0] == 201
    assert updated[0] == 200
    assert deleted[0] == 200
    assert deleted[1]["data"]["status"] == "INACTIVE"
