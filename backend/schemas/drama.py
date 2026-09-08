"""Drama and drama-association DTOs."""

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from schemas.common import SchemaModel

DramaStatus = Literal["DRAFT", "SERIALIZING", "COMPLETED", "INACTIVE"]
RelationStatus = Literal["ACTIVE", "INACTIVE"]
ActorRoleType = Literal["LEAD", "SUPPORTING", "GUEST", "OTHER"]
CompanyRelationType = Literal[
    "PRODUCER",
    "PRODUCTION",
    "DISTRIBUTOR",
    "CO_PRODUCTION",
    "OTHER",
]


class DramaCreate(SchemaModel):
    """Editable creation fields; drama_code is generated outside the client DTO."""

    drama_name: str = Field(min_length=1, max_length=200)
    synopsis: str | None = None
    episode_count: int | None = Field(default=None, gt=0, le=65535)
    episode_duration_seconds: int | None = Field(default=None, gt=0)
    premiere_date: date | None = None
    status: DramaStatus = "DRAFT"


class DramaUpdate(SchemaModel):
    """Mutable drama fields; identifiers and audit timestamps are excluded."""

    drama_name: str | None = Field(default=None, min_length=1, max_length=200)
    synopsis: str | None = None
    episode_count: int | None = Field(default=None, gt=0, le=65535)
    episode_duration_seconds: int | None = Field(default=None, gt=0)
    premiere_date: date | None = None
    status: DramaStatus | None = None


class DramaResponse(SchemaModel):
    drama_id: int = Field(ge=1)
    drama_code: str = Field(min_length=1, max_length=32)
    drama_name: str = Field(min_length=1, max_length=200)
    synopsis: str | None = None
    episode_count: int | None = Field(default=None, gt=0, le=65535)
    episode_duration_seconds: int | None = Field(default=None, gt=0)
    premiere_date: date | None = None
    status: DramaStatus
    created_at: datetime
    updated_at: datetime


class DramaActorCreate(SchemaModel):
    drama_id: int = Field(ge=1)
    actor_id: int = Field(ge=1)
    role_name: str | None = Field(default=None, max_length=100)
    role_type: ActorRoleType = "OTHER"
    billing_order: int | None = Field(default=None, gt=0, le=65535)
    relation_status: RelationStatus = "ACTIVE"


class DramaActorUpdate(SchemaModel):
    role_name: str | None = Field(default=None, max_length=100)
    role_type: ActorRoleType | None = None
    billing_order: int | None = Field(default=None, gt=0, le=65535)
    relation_status: RelationStatus | None = None


class DramaActorResponse(SchemaModel):
    drama_actor_id: int = Field(ge=1)
    drama_id: int = Field(ge=1)
    actor_id: int = Field(ge=1)
    role_name: str | None = Field(default=None, max_length=100)
    role_type: ActorRoleType
    billing_order: int | None = Field(default=None, gt=0, le=65535)
    relation_status: RelationStatus
    created_at: datetime
    updated_at: datetime


class DramaDirectorCreate(SchemaModel):
    drama_id: int = Field(ge=1)
    director_id: int = Field(ge=1)
    relation_status: RelationStatus = "ACTIVE"


class DramaDirectorUpdate(SchemaModel):
    relation_status: RelationStatus | None = None


class DramaDirectorResponse(SchemaModel):
    drama_director_id: int = Field(ge=1)
    drama_id: int = Field(ge=1)
    director_id: int = Field(ge=1)
    relation_status: RelationStatus
    created_at: datetime
    updated_at: datetime


class DramaCompanyCreate(SchemaModel):
    drama_id: int = Field(ge=1)
    company_id: int = Field(ge=1)
    relation_type: CompanyRelationType
    relation_status: RelationStatus = "ACTIVE"


class DramaCompanyUpdate(SchemaModel):
    relation_status: RelationStatus | None = None


class DramaCompanyResponse(SchemaModel):
    drama_company_id: int = Field(ge=1)
    drama_id: int = Field(ge=1)
    company_id: int = Field(ge=1)
    relation_type: CompanyRelationType
    relation_status: RelationStatus
    created_at: datetime
    updated_at: datetime


class DramaTagCreate(SchemaModel):
    drama_id: int = Field(ge=1)
    tag_id: int = Field(ge=1)
    relation_status: RelationStatus = "ACTIVE"


class DramaTagUpdate(SchemaModel):
    relation_status: RelationStatus | None = None


class DramaTagResponse(SchemaModel):
    drama_tag_id: int = Field(ge=1)
    drama_id: int = Field(ge=1)
    tag_id: int = Field(ge=1)
    relation_status: RelationStatus
    created_at: datetime
    updated_at: datetime
