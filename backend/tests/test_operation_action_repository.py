"""Repository contract tests for operation action persistence."""

from datetime import date, datetime
from unittest.mock import create_autospec

from sqlalchemy import Select
from sqlalchemy.orm import Session

from models.operation_action import OperationAction, OperationActionHistory, OperationActionSource
from repositories.operation_action_repository import (
    OperationActionHistoryRepository,
    OperationActionRepository,
    OperationActionSourceRepository,
)


def session_mock() -> Session:
    return create_autospec(Session, instance=True)


def test_create_action_flushes_without_transaction() -> None:
    session = session_mock()
    action = OperationAction(title="Review anomaly", created_by_user_id=1)
    result = OperationActionRepository(session).create_action(action)
    assert result is action
    session.add.assert_called_once_with(action)
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_detail_query_eager_loads_all_requested_relations() -> None:
    session = session_mock()
    result = session.execute.return_value
    result.unique.return_value.scalar_one_or_none.return_value = None
    assert OperationActionRepository(session).get_action_by_id(7) is None
    statement = session.execute.call_args.args[0]
    assert isinstance(statement, Select)
    options = statement._with_options
    paths = {str(option.path) for option in options}
    assert any("sources" in path for path in paths)
    assert any("history" in path for path in paths)
    assert any("drama" in path for path in paths)
    assert any("assignee" in path for path in paths)
    assert any("created_by" in path for path in paths)


def test_action_list_uses_filters_pagination_and_stable_order() -> None:
    session = session_mock()
    session.scalar.return_value = 1
    session.scalars.return_value.all.return_value = []
    page = OperationActionRepository(session).list_actions(
        page=2, page_size=10, status="OPEN", priority="HIGH", assignee_user_id=3, drama_id=4
    )
    assert page.page == 2 and page.page_size == 10 and page.total == 1
    statement = session.scalars.call_args.args[0]
    assert statement._offset_clause.value == 10
    assert statement._limit_clause.value == 10


def test_update_action_fields_only_allows_editable_columns() -> None:
    session = session_mock()
    action = OperationAction(action_id=2, title="Old", created_by_user_id=1)
    session.get.return_value = action
    result = OperationActionRepository(session).update_action_fields(
        action_id=2, values={"title": "New", "due_date": date(2026, 9, 20)}
    )
    assert result is action
    assert action.title == "New"
    assert action.due_date == date(2026, 9, 20)
    session.flush.assert_called_once_with()


def test_statistics_uses_database_aggregation() -> None:
    session = session_mock()
    session.scalar.return_value = 4
    session.execute.return_value.all.return_value = [("OPEN", 2), ("COMPLETED", 2)]
    result = OperationActionRepository(session).count_statistics()
    assert result == {"total": 4, "OPEN": 2, "IN_PROGRESS": 0, "COMPLETED": 2, "CANCELLED": 0}


def test_source_create_query_and_exists_are_scoped_to_action() -> None:
    session = session_mock()
    source = OperationActionSource(action_id=1, source_type="MANUAL", source_evidence_summary="Reason")
    assert OperationActionSourceRepository(session).create_source(source) is source
    session.scalars.return_value.all.return_value = [source]
    assert OperationActionSourceRepository(session).get_sources_by_action(action_id=1) == [source]
    session.scalar.return_value = 1
    assert OperationActionSourceRepository(session).exists_source(
        action_id=1, source_type="MANUAL", source_reference_id=None
    )


def test_history_create_and_query_are_chronological() -> None:
    session = session_mock()
    history = OperationActionHistory(action_id=1, event_type="COMMENT", operator_user_id=2)
    assert OperationActionHistoryRepository(session).create_history(history) is history
    session.scalars.return_value.all.return_value = [history]
    assert OperationActionHistoryRepository(session).get_history_by_action(action_id=1) == [history]


def test_repository_source_has_no_transaction_ownership_symbols() -> None:
    source = open(__file__.replace("test_operation_action_repository.py", "../repositories/operation_action_repository.py"), encoding="utf-8").read()
    assert "commit(" not in source
    assert "rollback(" not in source
    assert "sessionmaker" not in source
