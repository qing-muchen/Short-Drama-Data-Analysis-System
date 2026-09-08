"""Import job and import error DTOs."""

from datetime import datetime
from typing import Literal

from pydantic import Field

from schemas.common import SchemaModel

ImportType = Literal["MASTER_DATA", "SNAPSHOT"]
ImportJobStatus = Literal[
    "PENDING_VALIDATION",
    "VALIDATION_FAILED",
    "READY",
    "IMPORTING",
    "COMPLETED",
    "COMPLETED_WITH_ERRORS",
    "FAILED",
]
ImportFileFormat = Literal["CSV", "XLSX"]


class ImportJobCreate(SchemaModel):
    """File metadata accepted before the Service derives audit/lifecycle fields."""

    import_type: ImportType
    original_filename: str = Field(min_length=1, max_length=255)
    file_format: ImportFileFormat
    file_hash: str | None = Field(default=None, min_length=64, max_length=64)


class ImportJobUpdate(SchemaModel):
    """Import lifecycle fields are Service-owned, not client-editable."""


class ImportConfirmRequest(SchemaModel):
    """Explicit administrator confirmation for the staged valid row set."""

    confirm: Literal[True]


class ImportJobResponse(SchemaModel):
    import_job_id: int = Field(ge=1)
    initiated_by_user_id: int = Field(ge=1)
    import_type: ImportType
    status: ImportJobStatus
    original_filename: str = Field(min_length=1, max_length=255)
    file_format: ImportFileFormat
    file_hash: str | None = Field(default=None, min_length=64, max_length=64)
    total_rows: int = Field(ge=0)
    valid_rows: int = Field(ge=0)
    error_rows: int = Field(ge=0)
    imported_rows: int = Field(ge=0)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ImportErrorCreate(SchemaModel):
    """Internal validation result DTO, never a free-form client error."""

    import_job_id: int = Field(ge=1)
    source_row_number: int | None = Field(default=None, gt=0)
    column_name: str | None = Field(default=None, max_length=128)
    error_code: str = Field(min_length=1, max_length=64)
    error_message: str = Field(min_length=1, max_length=1000)
    raw_value: str | None = None


class ImportErrorUpdate(SchemaModel):
    """Import errors are append-only validation evidence."""


class ImportErrorResponse(SchemaModel):
    import_error_id: int = Field(ge=1)
    import_job_id: int = Field(ge=1)
    source_row_number: int | None = Field(default=None, gt=0)
    column_name: str | None = Field(default=None, max_length=128)
    error_code: str = Field(min_length=1, max_length=64)
    error_message: str = Field(min_length=1, max_length=1000)
    raw_value: str | None = None
    created_at: datetime
