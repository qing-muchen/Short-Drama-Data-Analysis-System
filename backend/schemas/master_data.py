"""Actor, director, company, and tag DTOs."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from schemas.common import SchemaModel

EntityStatus = Literal["ACTIVE", "INACTIVE"]


class ActorCreate(SchemaModel):
    actor_name: str = Field(min_length=1, max_length=100)
    profile_note: str | None = None
    status: EntityStatus = "ACTIVE"


class ActorUpdate(SchemaModel):
    actor_name: str | None = Field(default=None, min_length=1, max_length=100)
    profile_note: str | None = None
    status: EntityStatus | None = None


class ActorResponse(SchemaModel):
    actor_id: int = Field(ge=1)
    actor_name: str = Field(min_length=1, max_length=100)
    profile_note: str | None = None
    status: EntityStatus
    created_at: datetime
    updated_at: datetime


class DirectorCreate(SchemaModel):
    director_name: str = Field(min_length=1, max_length=100)
    profile_note: str | None = None
    status: EntityStatus = "ACTIVE"


class DirectorUpdate(SchemaModel):
    director_name: str | None = Field(default=None, min_length=1, max_length=100)
    profile_note: str | None = None
    status: EntityStatus | None = None


class DirectorResponse(SchemaModel):
    director_id: int = Field(ge=1)
    director_name: str = Field(min_length=1, max_length=100)
    profile_note: str | None = None
    status: EntityStatus
    created_at: datetime
    updated_at: datetime


class CompanyCreate(SchemaModel):
    company_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: EntityStatus = "ACTIVE"


class CompanyUpdate(SchemaModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: EntityStatus | None = None


class CompanyResponse(SchemaModel):
    company_id: int = Field(ge=1)
    company_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: EntityStatus
    created_at: datetime
    updated_at: datetime


class TagCreate(SchemaModel):
    tag_name: str = Field(min_length=1, max_length=100)
    status: EntityStatus = "ACTIVE"


class TagUpdate(SchemaModel):
    tag_name: str | None = Field(default=None, min_length=1, max_length=100)
    status: EntityStatus | None = None


class TagResponse(SchemaModel):
    tag_id: int = Field(ge=1)
    tag_name: str = Field(min_length=1, max_length=100)
    status: EntityStatus
    created_at: datetime
    updated_at: datetime
