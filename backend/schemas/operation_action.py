"""Pydantic DTOs for the operation action workflow API."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from schemas.common import PageResponse, ResponseModel, SchemaModel

OperationActionStatus = Literal["OPEN", "IN_PROGRESS", "COMPLETED", "CANCELLED"]
OperationActionPriority = Literal["LOW", "MEDIUM", "HIGH"]
OperationActionSourceType = Literal["ANOMALY", "QUALITY", "SCORE", "MANUAL"]
OperationActionEventType = Literal["CREATE", "ASSIGN", "STATUS_CHANGE", "COMMENT", "CLOSE"]


class ActionSourceRequest(SchemaModel):
    source_type: OperationActionSourceType
    source_reference_id: int | None = Field(default=None, ge=1)
    source_evidence_summary: str = Field(min_length=1, max_length=5000)
    source_analysis_as_of: datetime | None = None
    source_algorithm_version: str | None = Field(default=None, max_length=64)


class CreateActionRequest(SchemaModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    priority: OperationActionPriority = "MEDIUM"
    drama_id: int | None = Field(default=None, ge=1)
    assignee_user_id: int | None = Field(default=None, ge=1)
    due_date: date | None = None
    source: ActionSourceRequest | None = None


class UpdateStatusRequest(SchemaModel):
    new_status: OperationActionStatus
    comment: str | None = Field(default=None, max_length=5000)


class AssignActionRequest(SchemaModel):
    assignee_user_id: int = Field(ge=1)


class AddCommentRequest(SchemaModel):
    comment: str = Field(min_length=1, max_length=5000)


class ActionUserResponse(SchemaModel):
    user_id: int = Field(ge=1)
    username: str = Field(min_length=1, max_length=64)
    display_name: str | None = None
    role_code: Literal["ADMINISTRATOR", "USER"]


class SourceResponse(SchemaModel):
    source_id: int = Field(ge=1)
    source_type: OperationActionSourceType
    source_reference_id: int | None = None
    source_evidence_summary: str
    source_analysis_as_of: datetime | None = None
    source_algorithm_version: str | None = None
    created_at: datetime


class HistoryResponse(SchemaModel):
    history_id: int = Field(ge=1)
    event_type: OperationActionEventType
    old_status: OperationActionStatus | None = None
    new_status: OperationActionStatus | None = None
    operator_user_id: int = Field(ge=1)
    comment: str | None = None
    created_at: datetime


class OperationActionResponse(SchemaModel):
    action_id: int = Field(ge=1)
    drama_id: int | None = Field(default=None, ge=1)
    title: str
    description: str | None = None
    priority: OperationActionPriority
    status: OperationActionStatus
    assignee_user: ActionUserResponse | None = None
    creator_user: ActionUserResponse
    due_date: date | None = None
    created_at: datetime
    updated_at: datetime
    sources: list[SourceResponse] = Field(default_factory=list)
    history: list[HistoryResponse] = Field(default_factory=list)


class OperationActionStatisticsResponse(SchemaModel):
    total: int = Field(ge=0)
    OPEN: int = Field(ge=0)
    IN_PROGRESS: int = Field(ge=0)
    COMPLETED: int = Field(ge=0)
    CANCELLED: int = Field(ge=0)


__all__ = [
    "ActionSourceRequest", "AddCommentRequest", "AssignActionRequest",
    "CreateActionRequest", "HistoryResponse", "OperationActionEventType",
    "OperationActionPriority", "OperationActionResponse", "OperationActionSourceType",
    "OperationActionStatisticsResponse", "OperationActionStatus", "SourceResponse",
    "UpdateStatusRequest", "ActionUserResponse",
]
