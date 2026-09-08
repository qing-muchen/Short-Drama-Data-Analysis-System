"""Authentication and authorization exceptions safe for HTTP mapping."""

from services.exceptions import BusinessException


class AuthenticationException(BusinessException):
    """Credentials or access token cannot establish an active identity."""

    default_code = "AUTHENTICATION_FAILED"

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message)


class AuthorizationException(BusinessException):
    """An authenticated identity lacks the required role."""

    default_code = "FORBIDDEN"

    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(message)
