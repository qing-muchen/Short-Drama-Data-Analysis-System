"""Batch-import request and response DTOs."""

from datetime import datetime
from typing import Literal

from pydantic import Field, computed_field

from schemas.common import SchemaModel

BatchImportStatus = Literal[
    "CREATED", "UPLOADING", "VALIDATING", "READY", "IMPORTING",
    "COMPLETED", "VALIDATION_FAILED", "IMPORT_FAILED",
]
BatchFileType = Literal["MASTER_DATA", "DRAMA_TAGS", "DRAMA_PLATFORMS", "SNAPSHOT"]


class ImportBatchCreate(SchemaModel):
    batch_code: str | None = Field(default=None, min_length=1, max_length=64)


class ImportBatchConfirmRequest(SchemaModel):
    confirm: Literal[True]


class ImportBatchFileResponse(SchemaModel):
    import_job_id: int = Field(ge=1)
    batch_sequence: int = Field(ge=1)
    batch_file_type: BatchFileType
    original_filename: str = Field(min_length=1, max_length=255)
    file_format: Literal["CSV"]
    file_hash: str = Field(min_length=64, max_length=64)
    status: str
    total_rows: int = Field(ge=0)
    valid_rows: int = Field(ge=0)
    error_rows: int = Field(ge=0)
    imported_rows: int = Field(ge=0)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @computed_field(return_type=int)
    @property
    def skipped_rows(self) -> int:
        """Rows valid enough to identify, but omitted because they already exist."""

        return max(self.total_rows - self.valid_rows - self.error_rows, 0)


class ImportBatchResponse(SchemaModel):
    import_batch_id: int = Field(ge=1)
    batch_code: str = Field(min_length=1, max_length=64)
    status: BatchImportStatus
    created_by_user_id: int = Field(ge=1)
    total_files: int = Field(ge=0)
    total_rows: int = Field(ge=0)
    valid_rows: int = Field(ge=0)
    error_rows: int = Field(ge=0)
    imported_rows: int = Field(ge=0)
    validation_started_at: datetime | None = None
    validated_at: datetime | None = None
    import_started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    files: list[ImportBatchFileResponse] = Field(default_factory=list)

    @computed_field(return_type=int)
    @property
    def skipped_rows(self) -> int:
        return max(self.total_rows - self.valid_rows - self.error_rows, 0)
