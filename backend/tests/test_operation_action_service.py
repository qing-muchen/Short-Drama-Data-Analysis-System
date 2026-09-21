"""Service workflow tests for Phase 5 operation actions."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, create_autospec

import pytest
from sqlalchemy.orm import Session

from repositories.import_repository import OperationLogRepository
from repositories.operation_action_repository import (
    OperationActionHistoryRepository,
    OperationActionRepository,
    OperationActionSourceRepository,
)
from services.exceptions import ConflictException, ValidationException
from services.operation_action_service import ActionSourceInput, OperationActionService


def make_service(*, action_status: str = "OPEN", assignee_id: int | None = 2):
    session = create_autospec(Session, instance=True)
    action = SimpleNamespace(
        action_id=9, drama_id=7, status=action_status, assignee_user_id=assignee_id
    )
    actions = OperationActionRepository(session)
    actions.create_action = MagicMock(return_value=action)
    actions.get_action_by_id = MagicMock(return_value=action)
    actions.update_action_fields = MagicMock(return_value=action)
    actions.update_status = MagicMock(side_effect=lambda **kw: _set_status(action, kw["status"]))
    actions.list_actions = MagicMock(return_value="page")
    actions.count_statistics = MagicMock(return_value={"total": 1})
    sources = OperationActionSourceRepository(session)
    sources.find_open_action_id = MagicMock(return_value=None)
    sources.create_source = MagicMock(return_value="source")
    history = OperationActionHistoryRepository(session)
    history.create_history = MagicMock(return_value="history")
    logs = OperationLogRepository(session)
    logs.create = MagicMock(return_value="log")
    validator = MagicMock()
    service = OperationActionService(session, actions, sources, history, logs, validator)
    return service, session, action, actions, sources, history, logs, validator


def _set_status(action, status: str):
    action.status = status
    return action


def source_input(source_type: str = "ANOMALY", reference_id: int | None = 4):
    return ActionSourceInput(
        source_type=source_type,
        source_reference_id=reference_id,
        source_evidence_summary="Evidence snapshot",
        source_analysis_as_of=datetime(2026, 9, 20),
        source_algorithm_version="Rule-based Detection V1.0",
    )


def test_create_action_creates_source_history_log_and_commits_once() -> None:
    service, session, action, actions, sources, history, logs, validator = make_service()
    result = service.create_action(
        title="Investigate drop", description=None, priority="HIGH",
        drama_id=7, assignee_user_id=2, operator_user_id=1,
        operator_role="ADMINISTRATOR", source=source_input(),
    )
    assert result is action
    assert actions.create_action.call_args.args[0]["status"] == "OPEN"
    sources.create_source.assert_called_once()
    assert history.create_history.call_args.args[0]["event_type"] == "CREATE"
    logs.create.assert_called_once()
    validator.validate_source.assert_called_once()
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()


def test_global_manual_action_accepts_null_drama_and_reference() -> None:
    service, _, _, actions, sources, *_ = make_service()
    service.create_action(
        title="Global cleanup", description="Quality remediation", priority="MEDIUM",
        operator_user_id=1, operator_role="ADMINISTRATOR",
        source=source_input("MANUAL", None),
    )
    assert actions.create_action.call_args.args[0]["drama_id"] is None
    assert sources.create_source.call_args.args[0]["source_reference_id"] is None


def test_open_source_conflict_and_completed_source_reuse() -> None:
    service, session, *_rest = make_service()
    sources = _rest[2]
    sources.find_open_action_id.return_value = 88
    with pytest.raises(ConflictException):
        service.create_action(
            title="Duplicate", description=None, priority="LOW", operator_user_id=1,
            operator_role="ADMINISTRATOR", source=source_input(),
        )
    session.rollback.assert_called_once_with()
    sources.find_open_action_id.return_value = None
    service.create_action(
        title="New after closed", description=None, priority="LOW", operator_user_id=1,
        operator_role="ADMINISTRATOR", source=source_input(),
    )
    assert session.commit.call_count == 1


@pytest.mark.parametrize(
    ("old_status", "new_status"),
    [("OPEN", "IN_PROGRESS"), ("OPEN", "CANCELLED"), ("IN_PROGRESS", "COMPLETED"), ("IN_PROGRESS", "CANCELLED")],
)
def test_legal_status_transitions(old_status: str, new_status: str) -> None:
    service, session, action, actions, _, history, logs, _ = make_service(action_status=old_status)
    service.update_status(
        action_id=9, new_status=new_status, operator_user_id=1,
        operator_role="ADMINISTRATOR", comment="Handled",
    )
    actions.update_status.assert_called_once_with(action_id=9, status=new_status)
    expected_event = "CLOSE" if new_status in {"COMPLETED", "CANCELLED"} else "STATUS_CHANGE"
    assert history.create_history.call_args.args[0]["event_type"] == expected_event
    logs.create.assert_called_once()
    session.commit.assert_called_once_with()


@pytest.mark.parametrize(
    ("old_status", "new_status"),
    [("OPEN", "COMPLETED"), ("COMPLETED", "OPEN"), ("CANCELLED", "IN_PROGRESS")],
)
def test_illegal_or_terminal_status_transition_rolls_back(old_status: str, new_status: str) -> None:
    service, session, *_ = make_service(action_status=old_status)
    with pytest.raises(ValidationException):
        service.update_status(
            action_id=9, new_status=new_status, operator_user_id=1,
            operator_role="ADMINISTRATOR",
        )
    session.rollback.assert_called_once_with()


def test_assign_creates_history_and_operation_log() -> None:
    service, session, _, actions, _, history, logs, _ = make_service(assignee_id=2)
    service.assign_action(
        action_id=9, assignee_user_id=3, operator_user_id=1,
        operator_role="ADMINISTRATOR",
    )
    actions.update_action_fields.assert_called_once_with(action_id=9, values={"assignee_user_id": 3})
    assert history.create_history.call_args.args[0]["event_type"] == "ASSIGN"
    logs.create.assert_called_once()
    session.commit.assert_called_once_with()


def test_user_comment_does_not_change_action_state() -> None:
    service, session, action, actions, _, history, logs, _ = make_service(action_status="IN_PROGRESS")
    event = service.add_comment(
        action_id=9, operator_user_id=2, operator_role="USER", comment="Investigating",
    )
    assert event == "history"
    assert action.status == "IN_PROGRESS"
    actions.update_status.assert_not_called()
    payload = history.create_history.call_args.args[0]
    assert payload["event_type"] == "COMMENT"
    assert payload["old_status"] is None and payload["new_status"] is None
    logs.create.assert_called_once()
    session.commit.assert_called_once_with()


@pytest.mark.parametrize("failure_target", ["actions", "history", "logs"])
def test_create_failures_roll_back_atomically(failure_target: str) -> None:
    service, session, _, actions, _, history, logs, _ = make_service()
    target = {"actions": actions.create_action, "history": history.create_history, "logs": logs.create}[failure_target]
    target.side_effect = RuntimeError("boom")
    with pytest.raises(RuntimeError):
        service.create_action(
            title="Atomic", description=None, priority="LOW", operator_user_id=1,
            operator_role="ADMINISTRATOR",
        )
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


def test_query_methods_only_delegate() -> None:
    service, _, action, actions, *_ = make_service()
    assert service.get_action(9) is action
    assert service.list_actions(page=1, page_size=20) == "page"
    assert service.get_statistics() == {"total": 1}
    actions.list_actions.assert_called_once_with(page=1, page_size=20)


def test_service_source_has_no_orm_or_sql_access() -> None:
    source = open(__file__.replace("test_operation_action_service.py", "../services/operation_action_service.py"), encoding="utf-8").read()
    assert "from models" not in source
    assert "select(" not in source
    assert ".execute(" not in source
