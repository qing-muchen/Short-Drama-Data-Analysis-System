"""Pure Stage 1 validation for fixed import templates."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from pydantic import ValidationError as PydanticValidationError

from imports.parser import ParsedFile, ParsedRow
from imports.templates import MASTER_DATA_ENTITY_TYPES
from schemas.drama import DramaCreate
from schemas.master_data import ActorCreate, CompanyCreate, DirectorCreate, TagCreate
from schemas.platform import PlatformCreate

SHANGHAI = ZoneInfo("Asia/Shanghai")
COUNT_FIELDS = (
    "play_count",
    "like_count",
    "comment_count",
    "favorite_count",
    "share_count",
)


@dataclass(frozen=True, slots=True)
class ImportValidationError:
    source_row_number: int
    field_name: str | None
    error_type: str
    message: str
    raw_value: str | None = None


@dataclass(frozen=True, slots=True)
class ValidatedRecord:
    source_row_number: int
    entity_type: str
    values: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ValidationResult:
    total_rows: int
    records: tuple[ValidatedRecord, ...]
    errors: tuple[ImportValidationError, ...]

    @property
    def valid_rows(self) -> int:
        return len(self.records)

    @property
    def error_rows(self) -> int:
        return len({error.source_row_number for error in self.errors})


@dataclass(frozen=True, slots=True)
class ImportValidationContext:
    existing_drama_codes: frozenset[str] = frozenset()
    existing_platform_names: frozenset[str] = frozenset()
    existing_tag_names: frozenset[str] = frozenset()
    release_references: Mapping[tuple[str, str], Mapping[str, Any]] = None  # type: ignore[assignment]
    existing_snapshot_keys: frozenset[tuple[int, datetime]] = frozenset()
    received_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.release_references is None:
            object.__setattr__(self, "release_references", {})


class RowValidationFailure(ValueError):
    def __init__(self, field_name: str | None, error_type: str, message: str, raw: Any = None) -> None:
        super().__init__(message)
        self.field_name = field_name
        self.error_type = error_type
        self.message = message
        self.raw_value = _safe_raw(raw)


class ImportValidator:
    """Validate structure, types, references, uniqueness, and business values."""

    def validate(
        self,
        parsed: ParsedFile,
        *,
        import_type: str,
        context: ImportValidationContext,
    ) -> ValidationResult:
        if import_type == "MASTER_DATA":
            return self._validate_master_data(parsed, context)
        if import_type == "SNAPSHOT":
            return self._validate_snapshots(parsed, context)
        raise ValueError("Unsupported import type")

    def _validate_master_data(
        self,
        parsed: ParsedFile,
        context: ImportValidationContext,
    ) -> ValidationResult:
        records: list[ValidatedRecord] = []
        errors: list[ImportValidationError] = []
        seen: set[tuple[Any, ...]] = set()
        drama_codes = {_key(value) for value in context.existing_drama_codes}
        platform_names = {_key(value) for value in context.existing_platform_names}
        tag_names = {_key(value) for value in context.existing_tag_names}

        for row in parsed.rows:
            try:
                record = self._master_record(row)
                identity = self._master_identity(record)
                if identity in seen:
                    raise RowValidationFailure(None, "DUPLICATE_RECORD", "Duplicate row in import file")
                if record.entity_type == "DRAMA" and _key(record.values["drama_code"]) in drama_codes:
                    raise RowValidationFailure("drama_code", "BUSINESS_UNIQUENESS", "Drama code already exists")
                if record.entity_type == "PLATFORM" and _key(record.values["platform_name"]) in platform_names:
                    raise RowValidationFailure("name", "BUSINESS_UNIQUENESS", "Platform name already exists")
                if record.entity_type == "TAG" and _key(record.values["tag_name"]) in tag_names:
                    raise RowValidationFailure("name", "BUSINESS_UNIQUENESS", "Tag name already exists")
                seen.add(identity)
                records.append(record)
            except RowValidationFailure as error:
                errors.append(_to_error(row.source_row_number, error))
        return ValidationResult(len(parsed.rows), tuple(records), tuple(errors))

    def _master_record(self, row: ParsedRow) -> ValidatedRecord:
        entity_type = _required_text(row, "entity_type", max_length=32).upper()
        if entity_type not in MASTER_DATA_ENTITY_TYPES:
            raise RowValidationFailure("entity_type", "INVALID_STATUS", "Unsupported master data entity type", entity_type)
        name = _required_text(row, "name", max_length=200)
        description = _optional_text(row.values.get("description"))
        try:
            if entity_type == "DRAMA":
                status = (_optional_text(row.values.get("status")) or "DRAFT").upper()
                drama_code = _required_text(row, "drama_code", max_length=32)
                dto = DramaCreate(
                    drama_name=name,
                    synopsis=description,
                    episode_count=_optional_positive_int(row, "episode_count"),
                    episode_duration_seconds=_optional_positive_int(row, "episode_duration_seconds"),
                    premiere_date=_optional_date(row, "premiere_date"),
                    status=status,
                )
                values = dto.model_dump()
                values["drama_code"] = drama_code
            elif entity_type == "ACTOR":
                dto = ActorCreate(actor_name=name, profile_note=description, status=_entity_status(row))
                values = dto.model_dump()
            elif entity_type == "DIRECTOR":
                dto = DirectorCreate(director_name=name, profile_note=description, status=_entity_status(row))
                values = dto.model_dump()
            elif entity_type == "COMPANY":
                dto = CompanyCreate(company_name=name, description=description, status=_entity_status(row))
                values = dto.model_dump()
            elif entity_type == "PLATFORM":
                dto = PlatformCreate(platform_name=name, description=description, status=_entity_status(row))
                values = dto.model_dump()
            else:
                dto = TagCreate(tag_name=name, status=_entity_status(row))
                values = dto.model_dump()
        except PydanticValidationError as error:
            item = error.errors()[0]
            field = str(item.get("loc", ("row",))[0])
            raise RowValidationFailure(field, "FIELD_VALIDATION", "A field value is invalid", row.values.get(field)) from error
        return ValidatedRecord(row.source_row_number, entity_type, values)

    @staticmethod
    def _master_identity(record: ValidatedRecord) -> tuple[Any, ...]:
        if record.entity_type == "DRAMA":
            return ("DRAMA", _key(record.values["drama_code"]))
        if record.entity_type == "PLATFORM":
            return ("PLATFORM", _key(record.values["platform_name"]))
        if record.entity_type == "TAG":
            return ("TAG", _key(record.values["tag_name"]))
        return (record.entity_type, tuple(sorted((key, str(value)) for key, value in record.values.items())))

    def _validate_snapshots(
        self,
        parsed: ParsedFile,
        context: ImportValidationContext,
    ) -> ValidationResult:
        records: list[ValidatedRecord] = []
        errors: list[ImportValidationError] = []
        positions: dict[tuple[int, datetime], int] = {}
        invalidated: set[int] = set()
        now = _as_utc_naive(context.received_at or datetime.now(UTC))

        for row in parsed.rows:
            try:
                record = self._snapshot_record(row, context, now)
                key = (record.values["drama_platform_id"], record.values["snapshot_time"])
                if key in context.existing_snapshot_keys:
                    raise RowValidationFailure("snapshot_time", "CONFLICTING_SNAPSHOT", "A snapshot already exists for this release and time")
                if key in positions:
                    previous_index = positions[key]
                    previous = records[previous_index]
                    same_metrics = _metric_signature(previous.values) == _metric_signature(record.values)
                    if same_metrics:
                        raise RowValidationFailure("snapshot_time", "DUPLICATE_RECORD", "Duplicate snapshot row in import file")
                    invalidated.add(previous_index)
                    errors.append(
                        ImportValidationError(
                            previous.source_row_number,
                            "snapshot_time",
                            "CONFLICTING_SNAPSHOT",
                            "Conflicting snapshot rows share the same release and time",
                        )
                    )
                    raise RowValidationFailure("snapshot_time", "CONFLICTING_SNAPSHOT", "Conflicting snapshot rows share the same release and time")
                positions[key] = len(records)
                records.append(record)
            except RowValidationFailure as error:
                errors.append(_to_error(row.source_row_number, error))

        valid_records = tuple(record for index, record in enumerate(records) if index not in invalidated)
        return ValidationResult(len(parsed.rows), valid_records, tuple(errors))

    def _snapshot_record(
        self,
        row: ParsedRow,
        context: ImportValidationContext,
        now: datetime,
    ) -> ValidatedRecord:
        drama_code = _required_text(row, "drama_code", max_length=32)
        platform_name = _required_text(row, "platform_name", max_length=100)
        reference = context.release_references.get((_key(drama_code), _key(platform_name)))
        if reference is None:
            raise RowValidationFailure(None, "UNKNOWN_REFERENCE", "Drama and platform release relationship was not found")
        if reference.get("drama_status") == "INACTIVE" or reference.get("platform_status") != "ACTIVE":
            raise RowValidationFailure(None, "INACTIVE_REFERENCE", "The referenced drama or platform is inactive")
        if reference.get("release_status") != "ONLINE":
            raise RowValidationFailure(None, "INACTIVE_REFERENCE", "The referenced release is not online")

        snapshot_time = _required_datetime(row, "snapshot_time")
        if snapshot_time > now + timedelta(minutes=5):
            raise RowValidationFailure("snapshot_time", "INVALID_TIMESTAMP", "Snapshot time is in the future", row.values.get("snapshot_time"))
        values: dict[str, Any] = {
            "drama_code": drama_code,
            "platform_name": platform_name,
            "drama_platform_id": int(reference["drama_platform_id"]),
            "snapshot_time": snapshot_time,
        }
        for field in COUNT_FIELDS:
            values[field] = _required_nonnegative_int(row, field)
        values["ranking"] = _optional_positive_int(row, "ranking")
        return ValidatedRecord(row.source_row_number, "SNAPSHOT", values)


def _key(value: str) -> str:
    return value.strip().casefold()


def _safe_raw(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text[:500]


def _to_error(row_number: int, error: RowValidationFailure) -> ImportValidationError:
    return ImportValidationError(row_number, error.field_name, error.error_type, error.message, error.raw_value)


def _required_text(row: ParsedRow, field: str, *, max_length: int) -> str:
    value = _optional_text(row.values.get(field))
    if value is None:
        raise RowValidationFailure(field, "MISSING_REQUIRED_DATA", "A required value is missing")
    if len(value) > max_length:
        raise RowValidationFailure(field, "FIELD_TOO_LONG", f"Value exceeds {max_length} characters", value)
    return value


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _entity_status(row: ParsedRow) -> str:
    return (_optional_text(row.values.get("status")) or "ACTIVE").upper()


def _parse_integer(row: ParsedRow, field: str, *, required: bool) -> int | None:
    raw = row.values.get(field)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        if required:
            raise RowValidationFailure(field, "MISSING_REQUIRED_DATA", "A required value is missing")
        return None
    if isinstance(raw, bool):
        raise RowValidationFailure(field, "TYPE_ERROR", "An integer value is required", raw)
    try:
        if isinstance(raw, float):
            if not raw.is_integer():
                raise ValueError
            return int(raw)
        return int(str(raw).replace(",", "").strip())
    except (TypeError, ValueError) as error:
        raise RowValidationFailure(field, "TYPE_ERROR", "An integer value is required", raw) from error


def _required_nonnegative_int(row: ParsedRow, field: str) -> int:
    value = _parse_integer(row, field, required=True)
    assert value is not None
    if value < 0:
        raise RowValidationFailure(field, "INVALID_NEGATIVE_VALUE", "Cumulative counts cannot be negative", value)
    return value


def _optional_positive_int(row: ParsedRow, field: str) -> int | None:
    value = _parse_integer(row, field, required=False)
    if value is not None and value <= 0:
        error_type = "INVALID_RANKING" if field == "ranking" else "FIELD_VALIDATION"
        raise RowValidationFailure(field, error_type, "The value must be greater than zero", value)
    return value


def _optional_date(row: ParsedRow, field: str) -> date | None:
    raw = row.values.get(field)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if isinstance(raw, datetime):
        return raw.date()
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw).strip())
    except ValueError as error:
        raise RowValidationFailure(field, "TYPE_ERROR", "An ISO date is required", raw) from error


def _required_datetime(row: ParsedRow, field: str) -> datetime:
    raw = row.values.get(field)
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise RowValidationFailure(field, "MISSING_REQUIRED_DATA", "A required value is missing")
    if isinstance(raw, datetime):
        value = raw
    else:
        try:
            value = datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
        except ValueError as error:
            raise RowValidationFailure(field, "INVALID_TIMESTAMP", "An ISO date-time is required", raw) from error
    if value.tzinfo is None:
        value = value.replace(tzinfo=SHANGHAI)
    return _as_utc_naive(value)


def _as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _metric_signature(values: Mapping[str, Any]) -> tuple[Any, ...]:
    return tuple(values[field] for field in (*COUNT_FIELDS, "ranking"))
