"""Authentication request and safe response DTOs."""

from typing import Literal

from pydantic import Field, SecretStr

from schemas.common import SchemaModel
from schemas.user import UserResponse


class LoginRequest(SchemaModel):
    username: str = Field(min_length=1, max_length=64)
    password: SecretStr = Field(min_length=1, max_length=72)


class TokenResponse(SchemaModel):
    access_token: str = Field(min_length=1)
    token_type: Literal["bearer"] = "bearer"
    expires_in_seconds: int = Field(gt=0)


class CurrentUserResponse(UserResponse):
    """Named current-user contract, still excluding password_hash."""
