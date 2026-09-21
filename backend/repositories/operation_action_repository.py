"""Persistence access for operation actions and their audit records."""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from models.operation_action import (
    OperationAction,
    OperationActionHistory,
    OperationActionSource,
)
from repositories.base import BaseRepository, Page


ActionPayload = OperationAction | Mapping[str, Any]
SourcePayload = OperationActionSource | Mapping[str, Any]
HistoryPayload = OperationActionHistory | Mapping[str, Any]


class OperationActionRepository(BaseRepository[OperationAction]):
    """Store and query action state without authorization or transactions."""

    model = OperationAction

    def create_action(self, action: ActionPayload) -> OperationAction:
        entity = _as_entity(action, OperationAction)
        self.session.add(entity)
        self.session.flush()
        return entity

    def get_action_by_id(self, action_id: int) -> OperationAction | None:
        statement = (
            select(OperationAction)
            .options(
                joinedload(OperationAction.sources),
                joinedload(OperationAction.history),
                joinedload(OperationAction.drama),
                joinedload(OperationAction.assignee),
                joinedload(OperationAction.created_by),
            )
            .where(OperationAction.action_id == action_id)
        )
        return self.session.execute(statement).unique().scalar_one_or_none()

    def list_actions(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        priority: str | None = None,
        assignee_user_id: int | None = None,
        drama_id: int | None = None,
    ) -> Page[OperationAction]:
        statement = select(OperationAction).options(
            joinedload(OperationAction.drama),
            joinedload(OperationAction.assignee),
            joinedload(OperationAction.created_by),
        )
        filters = []
        if status is not None:
            filters.append(OperationAction.status == status)
        if priority is not None:
            filters.append(OperationAction.priority == priority)
        if assignee_user_id is not None:
            filters.append(OperationAction.assignee_user_id == assignee_user_id)
        if drama_id is not None:
            filters.append(OperationAction.drama_id == drama_id)
        statement = statement.where(*filters).order_by(
            OperationAction.created_at.desc(), OperationAction.action_id.desc()
        )
        return self.paginate(statement, page=page, page_size=page_size)

    def update_action_fields(
        self,
        *,
        action_id: int,
        values: Mapping[str, Any],
    ) -> OperationAction | None:
        allowed = {"title", "description", "priority", "assignee_user_id", "due_date"}
        unknown = set(values) - allowed
        if unknown:
            raise ValueError(f"Unsupported action fields: {sorted(unknown)}")
        entity = self.session.get(OperationAction, action_id)
        if entity is None:
            return None
        for key, value in values.items():
            setattr(entity, key, value)
        self.session.flush()
        return entity

    def count_statistics(self) -> dict[str, int]:
        statement = select(OperationAction.status, func.count(OperationAction.action_id)).group_by(
            OperationAction.status
        )
        result = {
            "total": int(self.session.scalar(select(func.count(OperationAction.action_id))) or 0),
            "OPEN": 0,
            "IN_PROGRESS": 0,
            "COMPLETED": 0,
            "CANCELLED": 0,
        }
        for status, count in self.session.execute(statement).all():
            result[str(status)] = int(count)
        return result


class OperationActionSourceRepository(BaseRepository[OperationActionSource]):
    """Persist and query logical source evidence snapshots."""

    model = OperationActionSource

    def create_source(self, source: SourcePayload) -> OperationActionSource:
        entity = _as_entity(source, OperationActionSource)
        self.session.add(entity)
        self.session.flush()
        return entity

    def get_sources_by_action(self, *, action_id: int) -> list[OperationActionSource]:
        statement = select(OperationActionSource).where(
            OperationActionSource.action_id == action_id
        ).order_by(
            OperationActionSource.created_at.asc(), OperationActionSource.source_id.asc()
        )
        return list(self.session.scalars(statement).all())

    def exists_source(
        self,
        *,
        action_id: int,
        source_type: str,
        source_reference_id: int | None,
    ) -> bool:
        statement = select(func.count(OperationActionSource.source_id)).where(
            OperationActionSource.action_id == action_id,
            OperationActionSource.source_type == source_type,
            OperationActionSource.source_reference_id == source_reference_id
            if source_reference_id is not None
            else OperationActionSource.source_reference_id.is_(None),
        )
        return bool(self.session.scalar(statement) or 0)


class OperationActionHistoryRepository(BaseRepository[OperationActionHistory]):
    """Persist and query immutable action process events."""

    model = OperationActionHistory

    def create_history(self, history: HistoryPayload) -> OperationActionHistory:
        entity = _as_entity(history, OperationActionHistory)
        self.session.add(entity)
        self.session.flush()
        return entity

    def get_history_by_action(self, *, action_id: int) -> list[OperationActionHistory]:
        statement = select(OperationActionHistory).where(
            OperationActionHistory.action_id == action_id
        ).order_by(
            OperationActionHistory.created_at.asc(), OperationActionHistory.history_id.asc()
        )
        return list(self.session.scalars(statement).all())


def _as_entity(value: Any, model: type[Any]) -> Any:
    if isinstance(value, model):
        return value
    if not isinstance(value, Mapping):
        raise TypeError(f"value must be {model.__name__} or a mapping")
    mapper = model.__mapper__
    unknown = set(value) - set(mapper.columns.keys())
    if unknown:
        raise ValueError(f"Unknown mapped columns: {sorted(unknown)}")
    return model(**dict(value))


__all__ = (
    "OperationActionRepository",
    "OperationActionSourceRepository",
    "OperationActionHistoryRepository",
)
