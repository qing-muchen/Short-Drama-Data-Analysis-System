"""JWT access-token creation and strict claim validation."""

from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from pydantic import BaseModel, ConfigDict, ValidationError

from auth.exceptions import AuthenticationException

JWT_ALGORITHM = "HS256"


class AccessTokenClaims(BaseModel):
    """Validated, non-sensitive access-token claims."""

    model_config = ConfigDict(extra="forbid")

    sub: str
    user_id: int
    username: str
    role: Literal["ADMINISTRATOR", "USER"]
    iat: int
    exp: int


def create_access_token(
    *,
    user_id: int,
    username: str,
    role: str,
    secret_key: str,
    expires_minutes: int,
) -> str:
    """Issue a signed access token containing identity and role claims only."""

    if expires_minutes < 1:
        raise ValueError("expires_minutes must be positive")
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "user_id": user_id,
        "username": username,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, *, secret_key: str) -> AccessTokenClaims:
    """Verify signature, expiration, required claims, and internal subject match."""

    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[JWT_ALGORITHM],
            options={
                "require": ["sub", "user_id", "username", "role", "iat", "exp"],
            },
        )
        claims = AccessTokenClaims.model_validate(payload)
        if claims.sub != str(claims.user_id):
            raise AuthenticationException()
        return claims
    except AuthenticationException:
        raise
    except (jwt.InvalidTokenError, ValidationError, TypeError, ValueError) as error:
        raise AuthenticationException() from error
