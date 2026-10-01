"""Batch file detection, relationship validation, upload staging, and writing."""

import csv
import hashlib
import io
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from imports.parser import ImportFileError, ParsedFile, ParsedRow, sanitize_filename
from imports.templates import MAX_IMPORT_FILE_SIZE_BYTES, TEMPLATES
from imports.validator import (
    ImportValidationContext,
    ImportValidationError,
    ImportValidator,
    ValidatedRecord,
    ValidationResult,
)
from repositories.import_repository import ImportDataRepository
from services.exceptions import ConflictException

BATCH_FILE_TYPES = ("MASTER_DATA", "DRAMA_TAGS", "DRAMA_PLATFORMS", "SNAPSHOT")
BATCH_PHASE_ORDER = {name: index for index, name in enumerate(BATCH_FILE_TYPES, start=1)}
SHANGHAI = ZoneInfo("Asia/Shanghai")


def detect_batch_file_type(*, filename: str, content: bytes) -> str:
    """Recognize one V1 batch file from its exact CSV header set."""

    safe_name = sanitize_filename(filename)
    if not safe_name.lower().endswith(".csv"):
        raise ImportFileError("UNSUPPORTED_FILE_TYPE", "Batch Import V1 only supports CSV files")
    if not content:
        raise ImportFileError("EMPTY_FILE", "The import file is empty")
    if len(content) > MAX_IMPORT_FILE_SIZE_BYTES:
        raise ImportFileError("FILE_TOO_LARGE", "The import file exceeds 20 MiB")
    try:
        first = next(csv.reader(io.StringIO(content.decode("utf-8-sig"), newline="")), None)
    except UnicodeDecodeError as error:
        raise ImportFileError("INVALID_ENCODING", "CSV must use UTF-8 encoding") from error
    except csv.Error as error:
        raise ImportFileError("CSV_PARSE_ERROR", "CSV content could not be parsed") from error
    if first is None:
        raise ImportFileError("EMPTY_FILE", "The import file is empty")
    headers = tuple(str(item).strip().lower() for item in first)
    if any(not item for item in headers) or len(set(headers)) != len(headers):
        raise ImportFileError("INVALID_HEADER", "Headers must be non-empty and unique")
    matches = [
        name
        for name in BATCH_FILE_TYPES
        if TEMPLATES[name].required_columns.issubset(headers)
        and set(headers).issubset(TEMPLATES[name].columns)
    ]
    if len(matches) != 1:
        raise ImportFileError(
            "TEMPLATE_MISMATCH",
            "The CSV header does not match one Batch Import V1 template",
        )
    return matches[0]


class BatchUploadStore:
    """Single-host V1 storage for uploaded source bytes before batch validation."""

    def __init__(self, base_directory: Path | None = None) -> None:
        self.base_directory = base_directory or (
            Path(tempfile.gettempdir())
            / "short_drama_data_analysis_system"
            / "batch_uploads"
        )

    def save(self, *, import_job_id: int, content: bytes) -> None:
        self.base_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.base_directory, prefix=f"{import_job_id}-", suffix=".tmp"
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
            os.replace(temporary_name, self._path(import_job_id))
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def load(self, *, import_job_id: int, expected_hash: str) -> bytes:
        try:
            content = self._path(import_job_id).read_bytes()
        except OSError as error:
            raise ImportFileError("STAGED_UPLOAD_MISSING", "The uploaded batch file is unavailable") from error
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise ImportFileError("STAGED_UPLOAD_MISMATCH", "The uploaded batch file failed its integrity check")
        return content

    def remove(self, import_job_id: int) -> None:
        try:
            self._path(import_job_id).unlink()
        except FileNotFoundError:
            pass

    def _path(self, import_job_id: int) -> Path:
        if import_job_id < 1:
            raise ValueError("import_job_id must be positive")
        return self.base_directory / f"{import_job_id}.csv"


@dataclass(frozen=True, slots=True)
class BatchReferenceProjection:
    dramas: Mapping[str, Mapping[str, Any]]
    platforms: Mapping[str, Mapping[str, Any]]
    tags: Mapping[str, Mapping[str, Any]]
    existing_drama_tag_pairs: frozenset[tuple[int, int]] = frozenset()
    existing_drama_platform_pairs: frozenset[tuple[int, int]] = frozenset()
    existing_platform_external_codes: frozenset[tuple[int, str]] = frozenset()


class BatchRelationValidator:
    """Validate V1 relationship files against DB plus staged master records."""

    def validate(
        self,
        parsed: ParsedFile,
        *,
        file_type: str,
        projection: BatchReferenceProjection,
    ) -> ValidationResult:
        if file_type == "DRAMA_TAGS":
            return self._validate_tags(parsed, projection)
        if file_type == "DRAMA_PLATFORMS":
            return self._validate_platforms(parsed, projection)
        raise ValueError("Unsupported batch relationship type")

    def _validate_tags(
        self, parsed: ParsedFile, projection: BatchReferenceProjection
    ) -> ValidationResult:
        records: list[ValidatedRecord] = []
        errors: list[ImportValidationError] = []
        seen: set[tuple[str, str]] = set()
        for row in parsed.rows:
            try:
                drama_code = _required_text(row, "drama_code", 32)
                tag_name = _required_text(row, "tag_name", 100)
                status = _required_choice(row, "relation_status", {"ACTIVE", "INACTIVE"})
                key = (_key(drama_code), _key(tag_name))
                if key in seen:
                    raise _RowFailure(None, "DUPLICATE_RECORD", "Duplicate drama-tag relationship")
                drama = projection.dramas.get(key[0])
                tag = projection.tags.get(key[1])
                if drama is None or tag is None:
                    raise _RowFailure(None, "UNKNOWN_REFERENCE", "Drama or tag was not found")
                if drama.get("id") is not None and tag.get("id") is not None and (
                    int(drama["id"]), int(tag["id"])
                ) in projection.existing_drama_tag_pairs:
                    raise _RowFailure(None, "DUPLICATE_RECORD", "Drama-tag relationship already exists")
                seen.add(key)
                records.append(
                    ValidatedRecord(
                        row.source_row_number,
                        "DRAMA_TAGS",
                        {"drama_code": drama_code, "tag_name": tag_name, "relation_status": status},
                    )
                )
            except _RowFailure as error:
                errors.append(_validation_error(row, error))
        return ValidationResult(len(parsed.rows), tuple(records), tuple(errors))

    def _validate_platforms(
        self, parsed: ParsedFile, projection: BatchReferenceProjection
    ) -> ValidationResult:
        records: list[ValidatedRecord] = []
        errors: list[ImportValidationError] = []
        seen_pairs: set[tuple[str, str]] = set()
        seen_external: set[tuple[str, str]] = set()
        for row in parsed.rows:
            try:
                drama_code = _required_text(row, "drama_code", 32)
                platform_name = _required_text(row, "platform_name", 100)
                platform_drama_code = _optional_text(row.values.get("platform_drama_code"), 100)
                status = _required_choice(row, "status", {"PLANNED", "ONLINE", "OFFLINE"})
                online_at = _optional_datetime(row.values.get("online_at"))
                if status != "PLANNED" and online_at is None:
                    raise _RowFailure("online_at", "MISSING_REQUIRED_DATA", "Online time is required")
                key = (_key(drama_code), _key(platform_name))
                if key in seen_pairs:
                    raise _RowFailure(None, "DUPLICATE_RECORD", "Duplicate drama-platform relationship")
                drama = projection.dramas.get(key[0])
                platform = projection.platforms.get(key[1])
                if drama is None or platform is None:
                    raise _RowFailure(None, "UNKNOWN_REFERENCE", "Drama or platform was not found")
                if status == "ONLINE" and (
                    drama.get("status") == "INACTIVE" or platform.get("status") != "ACTIVE"
                ):
                    raise _RowFailure(None, "INACTIVE_REFERENCE", "ONLINE release requires active references")
                if drama.get("id") is not None and platform.get("id") is not None and (
                    int(drama["id"]), int(platform["id"])
                ) in projection.existing_drama_platform_pairs:
                    raise _RowFailure(None, "DUPLICATE_RECORD", "Drama-platform relationship already exists")
                if platform_drama_code:
                    external_key = (key[1], _key(platform_drama_code))
                    if external_key in seen_external:
                        raise _RowFailure("platform_drama_code", "DUPLICATE_RECORD", "Duplicate platform drama code")
                    if platform.get("id") is not None and (
                        int(platform["id"]), external_key[1]
                    ) in projection.existing_platform_external_codes:
                        raise _RowFailure("platform_drama_code", "DUPLICATE_RECORD", "Platform drama code already exists")
                    seen_external.add(external_key)
                seen_pairs.add(key)
                records.append(
                    ValidatedRecord(
                        row.source_row_number,
                        "DRAMA_PLATFORMS",
                        {
                            "drama_code": drama_code,
                            "platform_name": platform_name,
                            "platform_drama_code": platform_drama_code,
                            "online_at": online_at,
                            "status": status,
                        },
                    )
                )
            except _RowFailure as error:
                errors.append(_validation_error(row, error))
        return ValidationResult(len(parsed.rows), tuple(records), tuple(errors))


class BatchImportWriter:
    """Write one fully validated batch in dependency order without committing."""

    def __init__(self, data: ImportDataRepository) -> None:
        self.data = data

    def write(
        self,
        *,
        files: Sequence[tuple[int, str, Sequence[dict[str, Any]]]],
        administrator_id: int,
    ) -> dict[int, int]:
        counts = {job_id: len(records) for job_id, _, records in files}
        by_type = {file_type: (job_id, records) for job_id, file_type, records in files}
        master_records = by_type.get("MASTER_DATA", (0, []))[1]
        self.data.create_masters(
            [
                (str(record["entity_type"]), _restore_values(dict(record["values"])))
                for record in master_records
            ]
        )

        tag_records = by_type.get("DRAMA_TAGS", (0, []))[1]
        platform_records = by_type.get("DRAMA_PLATFORMS", (0, []))[1]
        drama_codes = {
            str(record["values"]["drama_code"]) for record in (*tag_records, *platform_records)
        }
        tag_names = {str(record["values"]["tag_name"]) for record in tag_records}
        platform_names = {
            str(record["values"]["platform_name"]) for record in platform_records
        }
        drama_ids = self.data.resolve_drama_ids(drama_codes)
        tag_ids = self.data.resolve_tag_ids(tag_names)
        platform_ids = self.data.resolve_platform_ids(platform_names)

        tag_values = []
        for record in tag_records:
            values = record["values"]
            drama_id = drama_ids.get(_key(str(values["drama_code"])))
            tag_id = tag_ids.get(_key(str(values["tag_name"])))
            if drama_id is None or tag_id is None:
                raise ConflictException("A staged drama-tag reference no longer resolves")
            tag_values.append(
                {"drama_id": drama_id, "tag_id": tag_id, "relation_status": values["relation_status"]}
            )
        self.data.create_drama_tags(tag_values)

        platform_values = []
        for record in platform_records:
            values = _restore_values(dict(record["values"]))
            drama_id = drama_ids.get(_key(str(values["drama_code"])))
            platform_id = platform_ids.get(_key(str(values["platform_name"])))
            if drama_id is None or platform_id is None:
                raise ConflictException("A staged drama-platform reference no longer resolves")
            platform_values.append(
                {
                    "drama_id": drama_id,
                    "platform_id": platform_id,
                    "platform_drama_code": values.get("platform_drama_code"),
                    "online_at": values.get("online_at"),
                    "status": values["status"],
                }
            )
        self.data.create_drama_platforms(platform_values)

        snapshot_job_id, snapshot_records = by_type.get("SNAPSHOT", (0, []))
        if snapshot_records:
            codes = {str(record["values"]["drama_code"]) for record in snapshot_records}
            names = {str(record["values"]["platform_name"]) for record in snapshot_records}
            releases = self.data.snapshot_release_context(
                drama_codes=codes, platform_names=names
            )
            resolved: list[tuple[Mapping[str, Any], int]] = []
            keys: list[tuple[int, datetime]] = []
            for record in snapshot_records:
                values = _restore_values(dict(record["values"]))
                release = releases.get(
                    (_key(str(values["drama_code"])), _key(str(values["platform_name"])))
                )
                if release is None or release["drama_status"] == "INACTIVE" or release["platform_status"] != "ACTIVE" or release["release_status"] != "ONLINE":
                    raise ConflictException("A staged snapshot release is no longer eligible")
                values["drama_platform_id"] = int(release["drama_platform_id"])
                keys.append((values["drama_platform_id"], values["snapshot_time"]))
                resolved.append((values, snapshot_job_id))
            existing = self.data.existing_snapshot_keys(
                drama_platform_ids={item[0] for item in keys},
                start_time=min(item[1] for item in keys),
                end_time=max(item[1] for item in keys),
            )
            if existing.intersection(keys):
                raise ConflictException("A staged snapshot now conflicts with existing data")
            self.data.create_initial_snapshots(resolved, changed_by_user_id=administrator_id)
        return counts


class _RowFailure(ValueError):
    def __init__(self, field: str | None, code: str, message: str, raw: Any = None) -> None:
        super().__init__(message)
        self.field = field
        self.code = code
        self.message = message
        self.raw = None if raw is None else str(raw)[:500]


def _key(value: str) -> str:
    return value.strip().casefold()


def _optional_text(value: Any, max_length: int) -> str | None:
    text = None if value is None else str(value).strip()
    if not text:
        return None
    if len(text) > max_length:
        raise _RowFailure(None, "FIELD_TOO_LONG", f"Value exceeds {max_length} characters", value)
    return text


def _required_text(row: ParsedRow, field: str, max_length: int) -> str:
    value = _optional_text(row.values.get(field), max_length)
    if value is None:
        raise _RowFailure(field, "MISSING_REQUIRED_DATA", "A required value is missing")
    return value


def _required_choice(row: ParsedRow, field: str, choices: set[str]) -> str:
    value = _required_text(row, field, 32).upper()
    if value not in choices:
        raise _RowFailure(field, "FIELD_VALIDATION", "A field value is invalid", value)
    return value


def _optional_datetime(value: Any) -> datetime | None:
    text = None if value is None else str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise _RowFailure("online_at", "INVALID_TIMESTAMP", "An ISO date-time is required", value) from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(UTC).replace(tzinfo=None)


def _validation_error(row: ParsedRow, error: _RowFailure) -> ImportValidationError:
    return ImportValidationError(
        row.source_row_number, error.field, error.code, error.message, error.raw
    )


def _restore_values(values: dict[str, Any]) -> dict[str, Any]:
    if isinstance(values.get("snapshot_time"), str):
        values["snapshot_time"] = datetime.fromisoformat(values["snapshot_time"])
    if isinstance(values.get("online_at"), str):
        values["online_at"] = datetime.fromisoformat(values["online_at"])
    from datetime import date

    if isinstance(values.get("premiere_date"), str):
        values["premiere_date"] = date.fromisoformat(values["premiere_date"])
    values.pop("drama_platform_id", None)
    return values


def build_snapshot_validation_context(
    *,
    database_releases: Mapping[tuple[str, str], Mapping[str, Any]],
    projected_releases: Iterable[ValidatedRecord],
    projection: BatchReferenceProjection,
    existing_snapshot_keys: frozenset[tuple[int, datetime]],
) -> ImportValidationContext:
    releases = {key: dict(value) for key, value in database_releases.items()}
    synthetic_id = -1
    for record in projected_releases:
        values = record.values
        key = (_key(str(values["drama_code"])), _key(str(values["platform_name"])))
        drama = projection.dramas[key[0]]
        platform = projection.platforms[key[1]]
        releases[key] = {
            "drama_platform_id": synthetic_id,
            "drama_status": drama.get("status"),
            "platform_status": platform.get("status"),
            "release_status": values["status"],
        }
        synthetic_id -= 1
    return ImportValidationContext(
        release_references=releases,
        existing_snapshot_keys=existing_snapshot_keys,
    )
