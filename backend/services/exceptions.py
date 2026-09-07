"""Transport-neutral exception types exposed by the Service layer."""

from typing import Any, Mapping


class BusinessException(Exception):
    """Base exception for safe, intentional business-layer failures."""

    default_code = "BUSINESS_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.details = dict(details or {})


class NotFoundException(BusinessException):
    """Requested business resource does not exist."""

    default_code = "NOT_FOUND"


class ValidationException(BusinessException):
    """Input violates a Service-owned business validation rule."""

    default_code = "VALIDATION_ERROR"


class ConflictException(BusinessException):
    """Requested state transition conflicts with existing business data."""

    default_code = "BUSINESS_CONFLICT"


class PersistenceException(BusinessException):
    """Safe wrapper for database-layer failures crossing Service boundaries."""

    default_code = "PERSISTENCE_ERROR"

    def __init__(self, message: str = "The data operation could not be completed") -> None:
        super().__init__(message)
