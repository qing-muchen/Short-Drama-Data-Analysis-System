"""FastAPI HTTP Bearer security scheme for JWT access tokens."""

from fastapi.security import HTTPBearer

bearer_scheme = HTTPBearer(
    scheme_name="JWTBearer",
    description="JWT access token returned by /api/v1/auth/login",
    auto_error=False,
)
