"""Two-stage fixed-template import workflow and transaction boundary."""

import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from imports.importer import ImportBatchWriter, StagedImportError, StagedImportStore
from imports.parser import ImportFileError, ParsedFile, parse_import_file, sanitize_filename
from imports.validator import ImportValidationContext, ImportValidationError, ImportValidator
from repositories.base import Page
from repositories.import_repository import (
    ImportDataRepository,
    ImportErrorRepository,
    ImportJobRepository,
    OperationLogRepository,
)
from schemas.import_job import ImportJobCreate
from services.base import BaseService
from services.exceptions import (
    ConflictException,
    NotFoundException,
    PersistenceException,
)


class ImportService(BaseService):
    """Validate first, stage valid rows, then import on explicit confirmation."""

    def __init__(
        self,
        session: Session,
        jobs: ImportJobRepository,
        errors: ImportErrorRepository,
        data: ImportDataRepository,
        operation_logs: OperationLogRepository,
        *,
        validator: ImportValidator | None = None,
        stage_store: StagedImportStore | None = None,
    ) -> None:
        super().__init__(session, jobs, errors, data, operation_logs)  # type: ignore[arg-type]
        self.jobs = jobs
        self.errors = errors
        self.data = data
        self.operation_logs = operation_logs
        self.validator = validator or ImportValidator()
        self.stage_store = stage_store or StagedImportStore()

    def create_import_job(
        self,
        request: ImportJobCreate,
        *,
        content: bytes,
        administrator_id: int,
    ) -> Any:
        """Create, parse, validate, and stage a job without business writes."""

        source_hash = hashlib.sha256(content).hexdigest()
        try:
            safe_filename = sanitize_filename(request.original_filename)
        except ImportFileError as error:
            safe_filename = f"rejected-upload.{request.file_format.lower()}"
            job = self._create_pending_job(
                request,
                safe_filename=safe_filename,
                source_hash=source_hash,
                administrator_id=administrator_id,
            )
            return self._record_file_failure(job, error, administrator_id)

        job = self._create_pending_job(
            request,
            safe_filename=safe_filename,
            source_hash=source_hash,
            administrator_id=administrator_id,
        )
        try:
            parsed = parse_import_file(
                filename=safe_filename,
                file_format=request.file_format,
                content=content,
                import_type=request.import_type,
            )
        except ImportFileError as error:
            return self._record_file_failure(job, error, administrator_id)

        try:
            context = self._validation_context(parsed, request.import_type)
            result = self.validator.validate(
                parsed,
                import_type=request.import_type,
                context=context,
            )
        except Exception:
            self._mark_failed(job, administrator_id, "Import validation could not complete")
            raise
        final_status = "READY" if result.valid_rows else "VALIDATION_FAILED"
        try:
            if result.valid_rows:
                self.stage_store.save(
                    import_job_id=job.import_job_id,
                    import_type=request.import_type,
                    source_file_hash=source_hash,
                    records=result.records,
                )
        except (OSError, StagedImportError) as error:
            self._mark_failed(job, administrator_id, "Validated import staging failed")
            raise PersistenceException("The validated import could not be staged") from error

        try:
            with self.transaction():
                self.jobs.update(
                    job.import_job_id,
                    {
                        "status": final_status,
                        "total_rows": result.total_rows,
                        "valid_rows": result.valid_rows,
                        "error_rows": result.error_rows,
                        "finished_at": (
                            _utc_now() if final_status == "VALIDATION_FAILED" else None
                        ),
                    },
                )
                self._persist_errors(job.import_job_id, result.errors)
                self._audit(
                    job.import_job_id,
                    administrator_id,
                    operation_type="IMPORT_VALIDATE",
                    result_status="SUCCESS",
                    summary=(
                        f"Import validation completed: {result.valid_rows} valid rows, "
                        f"{result.error_rows} error rows"
                    ),
                )
        except Exception:
            self.stage_store.remove(job.import_job_id)
            self._mark_failed(job, administrator_id, "Import validation result could not be saved")
            raise
        return self.get_import_job(job.import_job_id)

    def get_import_job(self, import_job_id: int) -> Any:
        job = self.read(self.jobs.get_by_id, import_job_id)
        if job is None:
            raise NotFoundException(
                "Import job was not found", details={"import_job_id": import_job_id}
            )
        return job

    def list_import_errors(
        self,
        import_job_id: int,
        *,
        page: int,
        page_size: int,
    ) -> Page[Any]:
        self.get_import_job(import_job_id)
        return self.read(
            self.errors.list_by_job,
            import_job_id,
            page=page,
            page_size=page_size,
        )

    def confirm_import(self, import_job_id: int, *, administrator_id: int) -> Any:
        """Atomically write the staged valid set after administrator confirmation."""

        job = self.get_import_job(import_job_id)
        if job.status != "READY":
            raise ConflictException(
                "Only a READY import job can be confirmed",
                details={"status": job.status},
            )
        if not job.file_hash:
            raise ConflictException("The import job has no source integrity hash")
        try:
            staged_records = self.stage_store.load(
                import_job_id=job.import_job_id,
                import_type=job.import_type,
                source_file_hash=job.file_hash,
            )
        except StagedImportError as error:
            self._mark_failed(job, administrator_id, "Validated import stage unavailable")
            raise ConflictException("The validated import stage is unavailable") from error

        with self.transaction():
            if not self.jobs.claim_ready(job.import_job_id):
                raise ConflictException("The import job was already claimed")

        try:
            with self.transaction():
                imported_rows = ImportBatchWriter(self.data).write(
                    import_type=job.import_type,
                    staged_records=staged_records,
                    import_job_id=job.import_job_id,
                    administrator_id=administrator_id,
                )
                final_status = (
                    "COMPLETED_WITH_ERRORS" if job.error_rows > 0 else "COMPLETED"
                )
                self.jobs.update(
                    job.import_job_id,
                    {
                        "status": final_status,
                        "imported_rows": imported_rows,
                        "finished_at": _utc_now(),
                    },
                )
                self._audit(
                    job.import_job_id,
                    administrator_id,
                    operation_type="IMPORT_CONFIRM",
                    result_status="SUCCESS",
                    summary=f"Import committed atomically: {imported_rows} rows",
                )
        except Exception:
            self._mark_failed(job, administrator_id, "Import transaction rolled back")
            self.stage_store.remove(job.import_job_id)
            raise

        self.stage_store.remove(job.import_job_id)
        return self.get_import_job(job.import_job_id)

    def _create_pending_job(
        self,
        request: ImportJobCreate,
        *,
        safe_filename: str,
        source_hash: str,
        administrator_id: int,
    ) -> Any:
        with self.transaction():
            job = self.jobs.create(
                {
                    "initiated_by_user_id": administrator_id,
                    "import_type": request.import_type,
                    "status": "PENDING_VALIDATION",
                    "original_filename": safe_filename,
                    "file_format": request.file_format,
                    "file_hash": source_hash,
                    "total_rows": 0,
                    "valid_rows": 0,
                    "error_rows": 0,
                    "imported_rows": 0,
                    "started_at": _utc_now(),
                    "finished_at": None,
                }
            )
        return job

    def _record_file_failure(
        self,
        job: Any,
        error: ImportFileError,
        administrator_id: int,
    ) -> Any:
        with self.transaction():
            self.jobs.update(
                job.import_job_id,
                {
                    "status": "VALIDATION_FAILED",
                    # A file-level failure creates evidence but no invalid data row.
                    "error_rows": 0,
                    "finished_at": _utc_now(),
                },
            )
            self.errors.create(
                {
                    "import_job_id": job.import_job_id,
                    "source_row_number": None,
                    "column_name": None,
                    "error_code": error.code,
                    "error_message": error.message,
                    "raw_value": None,
                }
            )
            self._audit(
                job.import_job_id,
                administrator_id,
                operation_type="IMPORT_VALIDATE",
                result_status="FAILURE",
                summary=f"Import validation failed: {error.code}",
            )
        return self.get_import_job(job.import_job_id)

    def _validation_context(
        self,
        parsed: ParsedFile,
        import_type: str,
    ) -> ImportValidationContext:
        if import_type == "MASTER_DATA":
            drama_codes, platform_names, tag_names = self.read(
                self.data.master_uniqueness_context
            )
            return ImportValidationContext(
                existing_drama_codes=frozenset(drama_codes),
                existing_platform_names=frozenset(platform_names),
                existing_tag_names=frozenset(tag_names),
            )

        drama_codes = {
            str(row.values.get("drama_code", "")).strip()
            for row in parsed.rows
            if row.values.get("drama_code")
        }
        platform_names = {
            str(row.values.get("platform_name", "")).strip()
            for row in parsed.rows
            if row.values.get("platform_name")
        }
        releases = self.read(
            self.data.snapshot_release_context,
            drama_codes=drama_codes,
            platform_names=platform_names,
        )
        preliminary = self.validator.validate(
            parsed,
            import_type="SNAPSHOT",
            context=ImportValidationContext(release_references=releases),
        )
        keys = [
            (record.values["drama_platform_id"], record.values["snapshot_time"])
            for record in preliminary.records
        ]
        existing: set[tuple[int, datetime]] = set()
        if keys:
            existing = self.read(
                self.data.existing_snapshot_keys,
                drama_platform_ids={key[0] for key in keys},
                start_time=min(key[1] for key in keys),
                end_time=max(key[1] for key in keys),
            )
        return ImportValidationContext(
            release_references=releases,
            existing_snapshot_keys=frozenset(existing),
        )

    def _persist_errors(
        self,
        import_job_id: int,
        errors: tuple[ImportValidationError, ...],
    ) -> None:
        if not errors:
            return
        self.errors.create_many(
            [
                {
                    "import_job_id": import_job_id,
                    "source_row_number": item.source_row_number,
                    "column_name": item.field_name,
                    "error_code": item.error_type,
                    "error_message": item.message,
                    "raw_value": item.raw_value,
                }
                for item in errors
            ]
        )

    def _mark_failed(
        self,
        job: Any,
        administrator_id: int,
        summary: str,
    ) -> None:
        with self.transaction():
            self.jobs.update(
                job.import_job_id,
                {"status": "FAILED", "finished_at": _utc_now()},
            )
            self._audit(
                job.import_job_id,
                administrator_id,
                operation_type="IMPORT_CONFIRM",
                result_status="FAILURE",
                summary=summary,
            )

    def _audit(
        self,
        import_job_id: int,
        administrator_id: int,
        *,
        operation_type: str,
        result_status: str,
        summary: str,
    ) -> None:
        self.operation_logs.create(
            {
                "actor_user_id": administrator_id,
                "target_import_job_id": import_job_id,
                "operation_type": operation_type,
                "result_status": result_status,
                "summary": summary,
            }
        )


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
