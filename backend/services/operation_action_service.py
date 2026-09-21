"""Business orchestration for operation action resolution workflows."""

from dataclasses import dataclass
from datetime import date, datetime
import json
from typing import Any, Protocol

from sqlalchemy.orm import Session

from repositories.base import Page
from repositories.import_repository import OperationLogRepository
from repositories.operation_action_repository import (
    OperationActionHistoryRepository,
    OperationActionRepository,
    OperationActionSourceRepository,
)
from services.base import BaseService
from services.exceptions import ConflictException, NotFoundException, ValidationException


OPEN_STATUSES = {"OPEN", "IN_PROGRESS"}
FINAL_STATUSES = {"COMPLETED", "CANCELLED"}
TRANSITIONS = {
    "OPEN": {"IN_PROGRESS", "CANCELLED"},
    "IN_PROGRESS": {"COMPLETED", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


class SourceValidationProvider(Protocol):
    """Read-only source validation without coupling to analysis Services."""

    def validate_source(
        self, *, source_type: str, source_reference_id: int | None, drama_id: int | None
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class ActionSourceInput:
    source_type: str
    source_reference_id: int | None
    source_evidence_summary: str
    source_analysis_as_of: datetime | None = None
    source_algorithm_version: str | None = None


class OperationActionService(BaseService):
    """Apply action workflow, authorization, auditing, and transaction rules."""

    def __init__(
        self,
        session: Session,
        actions: OperationActionRepository,
        sources: OperationActionSourceRepository,
        history: OperationActionHistoryRepository,
        operation_logs: OperationLogRepository,
        source_validator: SourceValidationProvider | None = None,
    ) -> None:
        super().__init__(session, actions, sources, history, operation_logs)
        self.actions = actions
        self.sources = sources
        self.history = history
        self.operation_logs = operation_logs
        self.source_validator = source_validator

    def create_action(
        self,
        *,
        title: str,
        description: str | None,
        priority: str,
        operator_user_id: int,
        operator_role: str,
        drama_id: int | None = None,
        assignee_user_id: int | None = None,
        due_date: date | None = None,
        source: ActionSourceInput | None = None,
    ) -> Any:
        self._require_admin(operator_role)
        if not title.strip():
            raise ValidationException("Action title cannot be empty")
        if priority not in {"LOW", "MEDIUM", "HIGH"}:
            raise ValidationException("Unsupported action priority")
        if source is not None:
            self._validate_source(source, drama_id=drama_id)

        with self.transaction():
            if source is not None:
                existing = self.sources.find_open_action_id(
                    source_type=source.source_type,
                    source_reference_id=source.source_reference_id,
                )
                if existing is not None:
                    raise ConflictException(
                        "An open action already exists for this source",
                        details={"action_id": existing},
                    )
            action = self.actions.create_action(
                {
                    "drama_id": drama_id,
                    "title": title.strip(),
                    "description": description,
                    "priority": priority,
                    "status": "OPEN",
                    "assignee_user_id": assignee_user_id,
                    "created_by_user_id": operator_user_id,
                    "due_date": due_date,
                }
            )
            if source is not None:
                self.sources.create_source(
                    {
                        "action_id": action.action_id,
                        "source_type": source.source_type,
                        "source_reference_id": source.source_reference_id,
                        "source_evidence_summary": source.source_evidence_summary.strip(),
                        "source_analysis_as_of": source.source_analysis_as_of,
                        "source_algorithm_version": source.source_algorithm_version,
                    }
                )
            self.history.create_history(
                {
                    "action_id": action.action_id,
                    "event_type": "CREATE",
                    "old_status": None,
                    "new_status": "OPEN",
                    "operator_user_id": operator_user_id,
                    "comment": "Action created",
                }
            )
            self._log(action, operator_user_id, "ACTION_CREATE", "Action created")
        return action

    def update_status(
        self,
        *,
        action_id: int,
        new_status: str,
        operator_user_id: int,
        operator_role: str,
        comment: str | None = None,
    ) -> Any:
        self._require_admin(operator_role)
        with self.transaction():
            action = self._require_action(action_id)
            self._validate_transition(action.status, new_status)
            old_status = action.status
            action = self.actions.update_status(action_id=action_id, status=new_status)
            if action is None:
                raise NotFoundException("Operation action not found")
            event_type = "CLOSE" if new_status in FINAL_STATUSES else "STATUS_CHANGE"
            self.history.create_history(
                {
                    "action_id": action_id,
                    "event_type": event_type,
                    "old_status": old_status,
                    "new_status": new_status,
                    "operator_user_id": operator_user_id,
                    "comment": comment,
                }
            )
            self._log(
                action,
                operator_user_id,
                "ACTION_STATUS_UPDATE",
                f"Action status changed from {old_status} to {new_status}",
            )
        return action

    def complete_action(
        self,
        *,
        action_id: int,
        operator_user_id: int,
        operator_role: str,
        comment: str,
    ) -> Any:
        if not comment.strip():
            raise ValidationException("Completion comment cannot be empty")
        return self.update_status(
            action_id=action_id,
            new_status="COMPLETED",
            operator_user_id=operator_user_id,
            operator_role=operator_role,
            comment=comment.strip(),
        )

    def assign_action(
        self,
        *,
        action_id: int,
        assignee_user_id: int,
        operator_user_id: int,
        operator_role: str,
    ) -> Any:
        self._require_admin(operator_role)
        with self.transaction():
            action = self._require_action(action_id)
            old_assignee = action.assignee_user_id
            action = self.actions.update_action_fields(
                action_id=action_id, values={"assignee_user_id": assignee_user_id}
            )
            if action is None:
                raise NotFoundException("Operation action not found")
            self.history.create_history(
                {
                    "action_id": action_id,
                    "event_type": "ASSIGN",
                    "old_status": None,
                    "new_status": None,
                    "operator_user_id": operator_user_id,
                    "comment": f"Assignee changed from {old_assignee} to {assignee_user_id}",
                }
            )
            self._log(action, operator_user_id, "ACTION_ASSIGN", "Action assignee updated")
        return action

    def add_comment(
        self,
        *,
        action_id: int,
        operator_user_id: int,
        operator_role: str,
        comment: str,
    ) -> Any:
        if operator_role not in {"USER", "ADMINISTRATOR"}:
            raise ValidationException("Unsupported operator role")
        if not comment.strip():
            raise ValidationException("Comment cannot be empty")
        with self.transaction():
            action = self._require_action(action_id)
            if operator_role == "USER" and action.assignee_user_id != operator_user_id:
                raise ValidationException("Only the assignee can comment on this action")
            event = self.history.create_history(
                {
                    "action_id": action_id,
                    "event_type": "COMMENT",
                    "old_status": None,
                    "new_status": None,
                    "operator_user_id": operator_user_id,
                    "comment": comment.strip(),
                }
            )
            self._log(action, operator_user_id, "ACTION_COMMENT", "Action comment added")
        return event

    def get_action(self, action_id: int) -> Any:
        action = self.read(self.actions.get_action_by_id, action_id)
        if action is None:
            raise NotFoundException("Operation action not found")
        return action

    def list_actions(self, **filters: Any) -> Page[Any]:
        return self.read(self.actions.list_actions, **filters)

    def get_statistics(self) -> dict[str, int]:
        return self.read(self.actions.count_statistics)

    def _require_action(self, action_id: int) -> Any:
        action = self.actions.get_action_by_id(action_id)
        if action is None:
            raise NotFoundException("Operation action not found")
        return action

    def _validate_source(self, source: ActionSourceInput, *, drama_id: int | None) -> None:
        if source.source_type not in {"ANOMALY", "QUALITY", "SCORE", "MANUAL"}:
            raise ValidationException("Unsupported action source type")
        if not source.source_evidence_summary.strip():
            raise ValidationException("Source evidence summary cannot be empty")
        if source.source_type == "MANUAL":
            if source.source_reference_id is not None:
                raise ValidationException("MANUAL source must not have a reference id")
        elif source.source_reference_id is None or source.source_reference_id < 1:
            raise ValidationException("Analysis source requires a positive reference id")
        if self.source_validator is not None:
            self.source_validator.validate_source(
                source_type=source.source_type,
                source_reference_id=source.source_reference_id,
                drama_id=drama_id,
            )

    @staticmethod
    def _validate_transition(old_status: str, new_status: str) -> None:
        if old_status not in TRANSITIONS or new_status not in TRANSITIONS[old_status]:
            raise ValidationException(f"Invalid action status transition: {old_status} -> {new_status}")

    @staticmethod
    def _require_admin(operator_role: str) -> None:
        if operator_role != "ADMINISTRATOR":
            raise ValidationException("Administrator permission required")

    def _log(self, action: Any, actor_id: int, operation_type: str, summary: str) -> None:
        detail = json.dumps({"action_id": action.action_id}, ensure_ascii=False, sort_keys=True)
        values: dict[str, Any] = {
            "actor_user_id": actor_id,
            "operation_type": operation_type,
            "result_status": "SUCCESS",
            "summary": summary,
            "detail": detail,
        }
        if action.drama_id is not None:
            values["target_drama_id"] = action.drama_id
        else:
            values["target_user_id"] = actor_id
        self.operation_logs.create(values)


__all__ = ("ActionSourceInput", "OperationActionService", "SourceValidationProvider")
