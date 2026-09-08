"""Platform and drama-platform release DTOs."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from schemas.common import SchemaModel

PlatformStatus = Literal["ACTIVE", "INACTIVE"]
DramaPlatformStatus = Literal["PLANNED", "ONLINE", "OFFLINE"]


class PlatformCreate(SchemaModel):
    platform_name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    status: PlatformStatus = "ACTIVE"


class PlatformUpdate(SchemaModel):
    platform_name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    status: PlatformStatus | None = None


class PlatformResponse(SchemaModel):
    platform_id: int = Field(ge=1)
    platform_name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    status: PlatformStatus
    created_at: datetime
    updated_at: datetime


class DramaPlatformCreate(SchemaModel):
    drama_id: int = Field(ge=1)
    platform_id: int = Field(ge=1)
    platform_drama_code: str | None = Field(default=None, max_length=100)
    online_at: datetime | None = None
    page_url: str | None = Field(default=None, max_length=2048)
    status: DramaPlatformStatus = "PLANNED"


class DramaPlatformUpdate(SchemaModel):
    platform_drama_code: str | None = Field(default=None, max_length=100)
    online_at: datetime | None = None
    page_url: str | None = Field(default=None, max_length=2048)
    status: DramaPlatformStatus | None = None


class DramaPlatformResponse(SchemaModel):
    drama_platform_id: int = Field(ge=1)
    drama_id: int = Field(ge=1)
    platform_id: int = Field(ge=1)
    platform_drama_code: str | None = Field(default=None, max_length=100)
    online_at: datetime | None = None
    page_url: str | None = Field(default=None, max_length=2048)
    status: DramaPlatformStatus
    created_at: datetime
    updated_at: datetime
