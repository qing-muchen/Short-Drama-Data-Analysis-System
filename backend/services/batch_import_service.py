"""Batch Import V1 orchestration and transaction boundaries."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping, Sequence
from uuid import uuid4

from sqlalchemy.orm import Session

from imports.batch import (
    BATCH_FILE_TYPES,
    BatchImportWriter,
    BatchReferenceProjection,
    BatchRelationValidator,
    BatchUploadStore,
    build_snapshot_validation_context,
    detect_batch_file_type,
)
from imports.importer import StagedImportError, StagedImportStore
from imports.parser import ImportFileError, ParsedFile, parse_import_file, sanitize_filename
from imports.validator import (
    ImportValidationContext,
    ImportValidationError,
    ImportValidator,
    ValidationResult,
    collect_master_primary_keys,
)
from repositories.import_repository import (
    ImportBatchRepository,
    ImportDataRepository,
    ImportErrorRepository,
    ImportJobRepository,
)
from schemas.import_batch import ImportBatchCreate
from services.base import BaseService
from services.exceptions import ConflictException, NotFoundException, PersistenceException, ValidationException

MAX_BATCH_FILES = len(BATCH_FILE_TYPES)


@dataclass(frozen=True, slots=True)
class UploadedBatchFile:
    filename: str
    content: bytes


@dataclass(slots=True)
class _FileValidation:
    job: Any
    parsed: ParsedFile | None = None
    result: ValidationResult | None = None
    file_error: ImportFileError | None = None


class BatchImportService(BaseService):
    """Coordinate an additive four-file-type batch workflow."""

    def __init__(
        self,
        session: Session,
        batches: ImportBatchRepository,
        jobs: ImportJobRepository,
        errors: ImportErrorRepository,
        data: ImportDataRepository,
        *,
        validator: ImportValidator | None = None,
        relation_validator: BatchRelationValidator | None = None,
        upload_store: BatchUploadStore | None = None,
        stage_store: StagedImportStore | None = None,
    ) -> None:
        super().__init__(session, batches, jobs, errors, data)  # type: ignore[arg-type]
        self.batches = batches
        self.jobs = jobs
        self.errors = errors
        self.data = data
        self.validator = validator or ImportValidator()
        self.relation_validator = relation_validator or BatchRelationValidator()
        self.upload_store = upload_store or BatchUploadStore()
        self.stage_store = stage_store or StagedImportStore()

    def create_batch(self, request: ImportBatchCreate, *, administrator_id: int) -> Any:
        batch_code = (request.batch_code or self._new_batch_code()).strip()
        if not batch_code:
            raise ValidationException("Batch code cannot be empty")
        if self.read(self.batches.get_by_code, batch_code) is not None:
            raise ConflictException("Batch code already exists")
        with self.transaction():
            batch = self.batches.create(
                {
                    "batch_code": batch_code,
                    "status": "CREATED",
                    "created_by_user_id": administrator_id,
                    "total_files": 0,
                    "total_rows": 0,
                    "valid_rows": 0,
                    "error_rows": 0,
                    "imported_rows": 0,
                }
            )
            batch_id = batch.import_batch_id
        return self.get_batch(batch_id)

    def get_batch(self, import_batch_id: int) -> Any:
        batch = self.read(self.batches.get_by_id, import_batch_id)
        if batch is None:
            raise NotFoundException(
                "Import batch was not found", details={"import_batch_id": import_batch_id}
            )
        return batch

    def upload_files(
        self,
        import_batch_id: int,
        files: Sequence[UploadedBatchFile],
        *,
        administrator_id: int,
    ) -> Any:
        batch = self.get_batch(import_batch_id)
        if batch.status not in {"CREATED", "UPLOADING"}:
            raise ConflictException(
                "Files can only be uploaded to a CREATED or UPLOADING batch",
                details={"status": batch.status},
            )
        if not files:
            raise ValidationException("At least one CSV file is required")
        existing_jobs = self.read(self.jobs.list_by_batch, import_batch_id)
        if len(existing_jobs) + len(files) > MAX_BATCH_FILES:
            raise ValidationException(f"A V1 batch accepts at most {MAX_BATCH_FILES} files")

        prepared: list[tuple[str, str, bytes, str]] = []
        existing_types = {str(job.batch_file_type) for job in existing_jobs}
        incoming_types: set[str] = set()
        for item in files:
            safe_name = sanitize_filename(item.filename)
            file_type = detect_batch_file_type(filename=safe_name, content=item.content)
            if file_type in existing_types or file_type in incoming_types:
                raise ConflictException(
                    "A batch accepts only one file of each type",
                    details={"batch_file_type": file_type},
                )
            incoming_types.add(file_type)
            prepared.append(
                (safe_name, file_type, item.content, hashlib.sha256(item.content).hexdigest())
            )

        saved_ids: list[int] = []
        try:
            with self.transaction():
                sequence = len(existing_jobs)
                for safe_name, file_type, content, source_hash in prepared:
                    sequence += 1
                    job = self.jobs.create(
                        {
                            "import_batch_id": import_batch_id,
                            "batch_sequence": sequence,
                            "batch_file_type": file_type,
                            "initiated_by_user_id": administrator_id,
                            "import_type": "SNAPSHOT" if file_type == "SNAPSHOT" else "MASTER_DATA",
                            "status": "PENDING_VALIDATION",
                            "original_filename": safe_name,
                            "file_format": "CSV",
                            "file_hash": source_hash,
                            "total_rows": 0,
                            "valid_rows": 0,
                            "error_rows": 0,
                            "imported_rows": 0,
                            "started_at": None,
                            "finished_at": None,
                        }
                    )
                    self.upload_store.save(import_job_id=job.import_job_id, content=content)
                    saved_ids.append(job.import_job_id)
                self.batches.update(
                    import_batch_id,
                    {"status": "UPLOADING", "total_files": len(existing_jobs) + len(prepared)},
                )
        except Exception:
            for job_id in saved_ids:
                self.upload_store.remove(job_id)
            raise
        return self.get_batch(import_batch_id)

    def validate_batch(self, import_batch_id: int, *, administrator_id: int) -> Any:
        try:
            return self._validate_batch_claimed(
                import_batch_id, administrator_id=administrator_id
            )
        except Exception:
            batch = self.get_batch(import_batch_id)
            if batch.status == "VALIDATING":
                self._mark_validation_failed(import_batch_id)
            raise

    def _validate_batch_claimed(
        self, import_batch_id: int, *, administrator_id: int
    ) -> Any:
        del administrator_id
        batch = self.get_batch(import_batch_id)
        if batch.status != "UPLOADING":
            raise ConflictException(
                "Only an UPLOADING batch can be validated", details={"status": batch.status}
            )
        now = _utc_now()
        with self.transaction():
            if not self.batches.claim_status(import_batch_id, "UPLOADING", "VALIDATING"):
                raise ConflictException("The import batch was already claimed for validation")
            self.batches.update(import_batch_id, {"validation_started_at": now})

        jobs = self.read(self.jobs.list_by_batch, import_batch_id)
        validations = {str(job.batch_file_type): _FileValidation(job) for job in jobs}
        for file_type, state in validations.items():
            try:
                content = self.upload_store.load(
                    import_job_id=state.job.import_job_id,
                    expected_hash=str(state.job.file_hash),
                )
                state.parsed = parse_import_file(
                    filename=state.job.original_filename,
                    file_format="CSV",
                    content=content,
                    import_type=file_type,
                )
            except ImportFileError as error:
                state.file_error = error

        master_state = validations.get("MASTER_DATA")
        master_result = None
        if master_state and master_state.parsed:
            drama_codes, platform_names, tag_names = self.read(
                self.data.master_uniqueness_context
            )
            existing_primary_keys = self.read(
                self.data.existing_master_primary_keys,
                collect_master_primary_keys(master_state.parsed),
            )
            master_result = self.validator.validate(
                master_state.parsed,
                import_type="MASTER_DATA",
                context=ImportValidationContext(
                    existing_drama_codes=frozenset(drama_codes),
                    existing_platform_names=frozenset(platform_names),
                    existing_tag_names=frozenset(tag_names),
                    existing_master_primary_keys={
                        entity_type: frozenset(values)
                        for entity_type, values in existing_primary_keys.items()
                    },
                    use_master_primary_keys=True,
                    skip_existing_master_data=True,
                ),
            )
            master_state.result = master_result

        reference_values = self._reference_values(validations)
        database_context = self.read(
            self.data.batch_reference_context,
            drama_codes=reference_values["drama_codes"],
            platform_names=reference_values["platform_names"],
            tag_names=reference_values["tag_names"],
        )
        projection = self._projection(database_context, master_result)

        for file_type in ("DRAMA_TAGS", "DRAMA_PLATFORMS"):
            state = validations.get(file_type)
            if state and state.parsed:
                state.result = self.relation_validator.validate(
                    state.parsed, file_type=file_type, projection=projection
                )

        snapshot_state = validations.get("SNAPSHOT")
        if snapshot_state and snapshot_state.parsed:
            codes = {
                str(row.values.get("drama_code", "")).strip()
                for row in snapshot_state.parsed.rows
                if row.values.get("drama_code")
            }
            names = {
                str(row.values.get("platform_name", "")).strip()
                for row in snapshot_state.parsed.rows
                if row.values.get("platform_name")
            }
            database_releases = self.read(
                self.data.snapshot_release_context,
                drama_codes=codes,
                platform_names=names,
            )
            platform_result = validations.get("DRAMA_PLATFORMS")
            projected_records = (
                platform_result.result.records
                if platform_result and platform_result.result is not None
                else ()
            )
            preliminary_context = build_snapshot_validation_context(
                database_releases=database_releases,
                projected_releases=projected_records,
                projection=projection,
                existing_snapshot_keys=frozenset(),
            )
            preliminary = self.validator.validate(
                snapshot_state.parsed,
                import_type="SNAPSHOT",
                context=preliminary_context,
            )
            keys = [
                (record.values["drama_platform_id"], record.values["snapshot_time"])
                for record in preliminary.records
                if int(record.values["drama_platform_id"]) > 0
            ]
            existing_keys = set()
            if keys:
                existing_keys = self.read(
                    self.data.existing_snapshot_keys,
                    drama_platform_ids={item[0] for item in keys},
                    start_time=min(item[1] for item in keys),
                    end_time=max(item[1] for item in keys),
                )
            snapshot_state.result = self.validator.validate(
                snapshot_state.parsed,
                import_type="SNAPSHOT",
                context=build_snapshot_validation_context(
                    database_releases=database_releases,
                    projected_releases=projected_records,
                    projection=projection,
                    existing_snapshot_keys=frozenset(existing_keys),
                ),
            )

        return self._finish_validation(import_batch_id, validations)

    def confirm_batch(self, import_batch_id: int, *, administrator_id: int) -> Any:
        batch = self.get_batch(import_batch_id)
        if batch.status != "READY":
            raise ConflictException(
                "Only a READY import batch can be confirmed", details={"status": batch.status}
            )
        jobs = self.read(self.jobs.list_by_batch, import_batch_id)
        staged_files: list[tuple[int, str, Sequence[dict[str, Any]]]] = []
        try:
            for job in jobs:
                staged_files.append(
                    (
                        job.import_job_id,
                        str(job.batch_file_type),
                        self.stage_store.load(
                            import_job_id=job.import_job_id,
                            import_type=str(job.batch_file_type),
                            source_file_hash=str(job.file_hash),
                        ),
                    )
                )
        except StagedImportError as error:
            self._mark_import_failed(import_batch_id, jobs)
            self._remove_stages(jobs)
            raise ConflictException("The validated batch stage is unavailable") from error

        started = _utc_now()
        with self.transaction():
            if not self.batches.claim_status(import_batch_id, "READY", "IMPORTING"):
                raise ConflictException("The import batch was already claimed")
            self.batches.update(import_batch_id, {"import_started_at": started})
            for job in jobs:
                self.jobs.update(job.import_job_id, {"status": "IMPORTING"})

        try:
            with self.transaction():
                counts = BatchImportWriter(self.data).write(
                    files=staged_files, administrator_id=administrator_id
                )
                finished = _utc_now()
                imported_rows = sum(counts.values())
                for job in jobs:
                    self.jobs.update(
                        job.import_job_id,
                        {
                            "status": "COMPLETED",
                            "imported_rows": counts[job.import_job_id],
                            "finished_at": finished,
                        },
                    )
                self.batches.update(
                    import_batch_id,
                    {
                        "status": "COMPLETED",
                        "imported_rows": imported_rows,
                        "completed_at": finished,
                    },
                )
        except Exception:
            self._mark_import_failed(import_batch_id, jobs)
            self._remove_stages(jobs)
            raise
        self._remove_stages(jobs)
        return self.get_batch(import_batch_id)

    def _finish_validation(
        self, import_batch_id: int, validations: Mapping[str, _FileValidation]
    ) -> Any:
        failed = any(
            state.file_error is not None
            or state.result is None
            or bool(state.result.errors)
            for state in validations.values()
        )
        if not failed:
            try:
                for file_type, state in validations.items():
                    assert state.result is not None
                    self.stage_store.save(
                        import_job_id=state.job.import_job_id,
                        import_type=file_type,
                        source_file_hash=str(state.job.file_hash),
                        records=state.result.records,
                    )
            except (OSError, StagedImportError) as error:
                failed = True
                for state in validations.values():
                    if state.file_error is None and state.result is not None:
                        state.file_error = ImportFileError(
                            "STAGING_FAILED", "Validated batch staging failed"
                        )
                self._remove_stages([state.job for state in validations.values()])
                staging_exception = error
            else:
                staging_exception = None
        else:
            staging_exception = None

        total_rows = sum(
            state.result.total_rows if state.result is not None else 0
            for state in validations.values()
        )
        valid_rows = sum(
            state.result.valid_rows if state.result is not None else 0
            for state in validations.values()
        )
        error_rows = sum(
            state.result.error_rows if state.result is not None else 0
            for state in validations.values()
        )
        finished = _utc_now()
        with self.transaction():
            for state in validations.values():
                result = state.result
                self.jobs.update(
                    state.job.import_job_id,
                    {
                        "status": "VALIDATION_FAILED" if failed else "READY",
                        "total_rows": result.total_rows if result else 0,
                        "valid_rows": result.valid_rows if result else 0,
                        "error_rows": result.error_rows if result else 0,
                        "started_at": finished,
                        "finished_at": finished if failed else None,
                    },
                )
                errors = list(result.errors) if result else []
                if state.file_error is not None:
                    self.errors.create(
                        {
                            "import_job_id": state.job.import_job_id,
                            "source_row_number": None,
                            "column_name": None,
                            "error_code": state.file_error.code,
                            "error_message": state.file_error.message,
                            "raw_value": None,
                        }
                    )
                if errors:
                    self.errors.create_many(
                        [
                            {
                                "import_job_id": state.job.import_job_id,
                                "source_row_number": error.source_row_number,
                                "column_name": error.field_name,
                                "error_code": error.error_type,
                                "error_message": error.message,
                                "raw_value": error.raw_value,
                            }
                            for error in errors
                        ]
                    )
            self.batches.update(
                import_batch_id,
                {
                    "status": "VALIDATION_FAILED" if failed else "READY",
                    "total_rows": total_rows,
                    "valid_rows": valid_rows,
                    "error_rows": error_rows,
                    "validated_at": finished,
                    "completed_at": finished if failed else None,
                },
            )
        if failed:
            self._remove_stages([state.job for state in validations.values()])
        if staging_exception is not None:
            raise PersistenceException("The validated batch could not be staged") from staging_exception
        return self.get_batch(import_batch_id)

    def _mark_import_failed(self, import_batch_id: int, jobs: Sequence[Any]) -> None:
        finished = _utc_now()
        with self.transaction():
            for job in jobs:
                self.jobs.update(
                    job.import_job_id,
                    {"status": "FAILED", "finished_at": finished},
                )
            self.batches.update(
                import_batch_id,
                {"status": "IMPORT_FAILED", "completed_at": finished},
            )

    def _mark_validation_failed(self, import_batch_id: int) -> None:
        finished = _utc_now()
        jobs = self.read(self.jobs.list_by_batch, import_batch_id)
        with self.transaction():
            for job in jobs:
                self.jobs.update(
                    job.import_job_id,
                    {
                        "status": "VALIDATION_FAILED",
                        "started_at": job.started_at or finished,
                        "finished_at": finished,
                    },
                )
            self.batches.update(
                import_batch_id,
                {
                    "status": "VALIDATION_FAILED",
                    "validated_at": finished,
                    "completed_at": finished,
                },
            )

    def _remove_stages(self, jobs: Sequence[Any]) -> None:
        for job in jobs:
            self.stage_store.remove(job.import_job_id)
            self.upload_store.remove(job.import_job_id)

    @staticmethod
    def _projection(
        database_context: Mapping[str, Any], master_result: ValidationResult | None
    ) -> BatchReferenceProjection:
        dramas = {key: dict(value) for key, value in database_context["dramas"].items()}
        platforms = {key: dict(value) for key, value in database_context["platforms"].items()}
        tags = {key: dict(value) for key, value in database_context["tags"].items()}
        if master_result:
            for record in master_result.records:
                if record.entity_type == "DRAMA":
                    dramas[_key(record.values["drama_code"])] = {
                        "id": None, "status": record.values["status"]
                    }
                elif record.entity_type == "PLATFORM":
                    platforms[_key(record.values["platform_name"])] = {
                        "id": None, "status": record.values["status"]
                    }
                elif record.entity_type == "TAG":
                    tags[_key(record.values["tag_name"])] = {
                        "id": None, "status": record.values["status"]
                    }
        return BatchReferenceProjection(
            dramas=dramas,
            platforms=platforms,
            tags=tags,
            existing_drama_tag_pairs=frozenset(database_context["drama_tag_pairs"]),
            existing_drama_platform_pairs=frozenset(database_context["drama_platform_pairs"]),
            existing_platform_external_codes=frozenset(database_context["platform_external_codes"]),
        )

    @staticmethod
    def _reference_values(
        validations: Mapping[str, _FileValidation]
    ) -> dict[str, set[str]]:
        result = {"drama_codes": set(), "platform_names": set(), "tag_names": set()}
        for state in validations.values():
            if state.parsed is None:
                continue
            for row in state.parsed.rows:
                if row.values.get("drama_code"):
                    result["drama_codes"].add(str(row.values["drama_code"]).strip())
                if row.values.get("platform_name"):
                    result["platform_names"].add(str(row.values["platform_name"]).strip())
                if row.values.get("tag_name"):
                    result["tag_names"].add(str(row.values["tag_name"]).strip())
        return result

    @staticmethod
    def _new_batch_code() -> str:
        return f"BATCH-{datetime.now(UTC):%Y%m%d%H%M%S}-{uuid4().hex[:8].upper()}"


def _key(value: Any) -> str:
    return str(value).strip().casefold()


def _utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
