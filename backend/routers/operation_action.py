"""HTTP endpoints for creating and resolving operation actions."""

from typing import Annotated, Any

from fastapi import APIRouter, Path, Query

from auth.dependencies import AdministratorDependency, AuthenticatedUserDependency
from routers.dependencies import OperationActionServiceDependency
from routers.errors import ERROR_RESPONSES
from schemas.common import PageResponse, ResponseModel
from schemas.operation_action import (
    ActionSourceRequest, AddCommentRequest, AssignActionRequest, CreateActionRequest,
    HistoryResponse, OperationActionResponse, OperationActionStatisticsResponse,
    SourceResponse, UpdateStatusRequest,
)

router = APIRouter(prefix="/operation-actions", tags=["operation-actions"], responses=ERROR_RESPONSES)


@router.post("", response_model=ResponseModel[OperationActionResponse])
def create_action(payload: CreateActionRequest, administrator: AdministratorDependency,
                  service: OperationActionServiceDependency) -> ResponseModel[OperationActionResponse]:
    source = None
    if payload.source is not None:
        source = _source_input(payload.source)
    entity = service.create_action(
        title=payload.title, description=payload.description, priority=payload.priority,
        drama_id=payload.drama_id, assignee_user_id=payload.assignee_user_id,
        due_date=payload.due_date, source=source,
        operator_user_id=administrator.user_id, operator_role=administrator.role_code,
    )
    return ResponseModel(data=_action_response(entity))


@router.get("/statistics", response_model=ResponseModel[OperationActionStatisticsResponse])
def get_statistics(current_user: AuthenticatedUserDependency,
                   service: OperationActionServiceDependency) -> ResponseModel[OperationActionStatisticsResponse]:
    del current_user
    return ResponseModel(data=OperationActionStatisticsResponse(**service.get_statistics()))


@router.get("", response_model=ResponseModel[PageResponse[OperationActionResponse]])
def list_actions(current_user: AuthenticatedUserDependency, service: OperationActionServiceDependency,
                 status: Annotated[str | None, Query()] = None,
                 priority: Annotated[str | None, Query()] = None,
                 assignee_user_id: Annotated[int | None, Query(ge=1)] = None,
                 drama_id: Annotated[int | None, Query(ge=1)] = None,
                 page: Annotated[int, Query(ge=1)] = 1,
                 page_size: Annotated[int, Query(ge=1, le=100)] = 20) -> ResponseModel[PageResponse[OperationActionResponse]]:
    del current_user
    result = service.list_actions(status=status, priority=priority, assignee_user_id=assignee_user_id,
                                  drama_id=drama_id, page=page, page_size=page_size)
    return ResponseModel(data=PageResponse(page=result.page, page_size=result.page_size, total=result.total,
                                           items=[_action_response(item) for item in result.items]))


@router.get("/{action_id}", response_model=ResponseModel[OperationActionResponse])
def get_action(action_id: Annotated[int, Path(ge=1)], current_user: AuthenticatedUserDependency,
               service: OperationActionServiceDependency) -> ResponseModel[OperationActionResponse]:
    del current_user
    return ResponseModel(data=_action_response(service.get_action(action_id)))


@router.patch("/{action_id}/status", response_model=ResponseModel[OperationActionResponse])
def update_status(action_id: Annotated[int, Path(ge=1)], payload: UpdateStatusRequest,
                  administrator: AdministratorDependency, service: OperationActionServiceDependency) -> ResponseModel[OperationActionResponse]:
    entity = service.update_status(action_id=action_id, new_status=payload.new_status,
                                   comment=payload.comment, operator_user_id=administrator.user_id,
                                   operator_role=administrator.role_code)
    return ResponseModel(data=_action_response(entity))


@router.patch("/{action_id}/assign", response_model=ResponseModel[OperationActionResponse])
def assign_action(action_id: Annotated[int, Path(ge=1)], payload: AssignActionRequest,
                  administrator: AdministratorDependency, service: OperationActionServiceDependency) -> ResponseModel[OperationActionResponse]:
    entity = service.assign_action(action_id=action_id, assignee_user_id=payload.assignee_user_id,
                                   operator_user_id=administrator.user_id, operator_role=administrator.role_code)
    return ResponseModel(data=_action_response(entity))


@router.post("/{action_id}/comments", response_model=ResponseModel[HistoryResponse])
def add_comment(action_id: Annotated[int, Path(ge=1)], payload: AddCommentRequest,
                current_user: AuthenticatedUserDependency, service: OperationActionServiceDependency) -> ResponseModel[HistoryResponse]:
    event = service.add_comment(action_id=action_id, comment=payload.comment,
                                operator_user_id=current_user.user_id, operator_role=current_user.role_code)
    return ResponseModel(data=HistoryResponse.model_validate(event))


def _source_input(payload: ActionSourceRequest) -> Any:
    from services.operation_action_service import ActionSourceInput
    return ActionSourceInput(**payload.model_dump())


def _user_response(user: Any) -> Any:
    if user is None:
        return None
    from schemas.operation_action import ActionUserResponse
    return ActionUserResponse.model_validate(user)


def _action_response(entity: Any) -> OperationActionResponse:
    return OperationActionResponse(
        action_id=entity.action_id, drama_id=entity.drama_id, title=entity.title,
        description=entity.description, priority=entity.priority, status=entity.status,
        assignee_user=_user_response(entity.assignee), creator_user=_user_response(entity.created_by),
        due_date=entity.due_date, created_at=entity.created_at, updated_at=entity.updated_at,
        sources=[SourceResponse.model_validate(item) for item in entity.sources],
        history=[HistoryResponse.model_validate(item) for item in entity.history],
    )


__all__ = ("router",)
