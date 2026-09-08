"""Safe HTTP mappings for transport-neutral Service exceptions."""

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from auth.exceptions import AuthenticationException, AuthorizationException
from schemas.common import ErrorResponse
from services.exceptions import (
    BusinessException,
    ConflictException,
    NotFoundException,
    PersistenceException,
    ValidationException,
)

ERROR_RESPONSES: dict[int, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "Business validation error"},
    404: {"model": ErrorResponse, "description": "Resource not found"},
    409: {"model": ErrorResponse, "description": "Business conflict"},
    422: {"model": ErrorResponse, "description": "Request validation error"},
    401: {"model": ErrorResponse, "description": "Authentication required"},
    403: {"model": ErrorResponse, "description": "Permission denied"},
    500: {"model": ErrorResponse, "description": "Safe persistence error"},
}


def _status_for(error: BusinessException) -> int:
    if isinstance(error, AuthenticationException):
        return 401
    if isinstance(error, AuthorizationException):
        return 403
    if isinstance(error, NotFoundException):
        return 404
    if isinstance(error, ValidationException):
        return 400
    if isinstance(error, ConflictException):
        return 409
    if isinstance(error, PersistenceException):
        return 500
    return 400


async def handle_business_exception(
    _request: Request,
    error: BusinessException,
) -> JSONResponse:
    payload = ErrorResponse(
        code=error.code,
        message=error.message,
        details=error.details or None,
    )
    headers = (
        {"WWW-Authenticate": "Bearer"}
        if isinstance(error, AuthenticationException)
        else None
    )
    return JSONResponse(
        status_code=_status_for(error),
        content=jsonable_encoder(payload),
        headers=headers,
    )


async def handle_request_validation(
    _request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    payload = ErrorResponse(
        code="REQUEST_VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": error.errors()},
    )
    return JSONResponse(status_code=422, content=jsonable_encoder(payload))


def install_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(BusinessException, handle_business_exception)
    app.add_exception_handler(RequestValidationError, handle_request_validation)
