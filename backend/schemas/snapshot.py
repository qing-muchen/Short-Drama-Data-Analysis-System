"""Observation-slot and immutable revision DTOs."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from schemas.common import SchemaModel

RevisionAction = Literal["INITIAL", "CORRECTION", "VOID"]


class DramaMetricSnapshotCreate(SchemaModel):
    """Ordinary slot input without revision pointer or import audit fields."""

    drama_platform_id: int = Field(ge=1)
    snapshot_time: datetime


class DramaMetricSnapshotUpdate(SchemaModel):
    """Slots have no ordinary client-editable fields after creation."""


class DramaMetricSnapshotResponse(SchemaModel):
    snapshot_id: int = Field(ge=1)
    drama_platform_id: int = Field(ge=1)
    snapshot_time: datetime
    current_revision_id: int | None = Field(default=None, ge=1)
    source_import_job_id: int | None = Field(default=None, ge=1)
    created_at: datetime
    updated_at: datetime


class DramaMetricSnapshotRevisionCreate(SchemaModel):
    """Metric payload only; Service derives version, action, chain, and actor."""

    play_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    favorite_count: int | None = Field(default=None, ge=0)
    share_count: int | None = Field(default=None, ge=0)
    ranking: int | None = Field(default=None, gt=0)
    change_reason: str | None = None


class DramaMetricSnapshotRevisionUpdate(SchemaModel):
    """Immutable revisions cannot be updated through a DTO."""


class DramaMetricSnapshotRevisionResponse(SchemaModel):
    snapshot_revision_id: int = Field(ge=1)
    snapshot_id: int = Field(ge=1)
    version_no: int = Field(ge=1)
    previous_revision_id: int | None = Field(default=None, ge=1)
    revision_action: RevisionAction
    play_count: int | None = Field(default=None, ge=0)
    like_count: int | None = Field(default=None, ge=0)
    comment_count: int | None = Field(default=None, ge=0)
    favorite_count: int | None = Field(default=None, ge=0)
    share_count: int | None = Field(default=None, ge=0)
    ranking: int | None = Field(default=None, gt=0)
    change_reason: str | None = None
    changed_by_user_id: int = Field(ge=1)
    changed_at: datetime
