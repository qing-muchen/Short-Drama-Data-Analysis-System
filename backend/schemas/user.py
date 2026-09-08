"""User request and response DTOs."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from schemas.common import SchemaModel

UserRole = Literal["ADMINISTRATOR", "USER"]
UserStatus = Literal["ACTIVE", "INACTIVE"]


class UserCreate(SchemaModel):
    """Editable user profile fields; credential input is a later security DTO."""

    username: str = Field(min_length=1, max_length=64)
    display_name: str | None = Field(default=None, max_length=100)
    role_code: UserRole = "USER"
    status: UserStatus = "ACTIVE"


class UserUpdate(SchemaModel):
    """Editable account fields; username and password hash are excluded."""

    display_name: str | None = Field(default=None, max_length=100)
    role_code: UserRole | None = None
    status: UserStatus | None = None


class UserResponse(SchemaModel):
    """Public-safe user representation without password_hash."""

    user_id: int = Field(ge=1)
    username: str = Field(min_length=1, max_length=64)
    display_name: str | None = Field(default=None, max_length=100)
    role_code: UserRole
    status: UserStatus
    last_login_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
