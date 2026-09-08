"""Validated-record staging and transaction-neutral batch writing."""

import hashlib
import hmac
import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from imports.validator import ValidatedRecord
from repositories.import_repository import ImportDataRepository
from services.exceptions import ConflictException, ValidationException


class StagedImportError(RuntimeError):
    """Raised when a validated stage file is missing or fails integrity checks."""


class StagedImportStore:
    """Store validated rows outside formal tables until administrator confirmation."""

    def __init__(self, base_directory: Path | None = None) -> None:
        self.base_directory = base_directory or (
            Path(tempfile.gettempdir())
            / "short_drama_data_analysis_system"
            / "import_stage"
        )

    def save(
        self,
        *,
        import_job_id: int,
        import_type: str,
        source_file_hash: str,
        records: Iterable[ValidatedRecord],
    ) -> None:
        self.base_directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        payload = {
            "import_job_id": import_job_id,
            "import_type": import_type,
            "source_file_hash": source_file_hash,
            "records": [
                {
                    "source_row_number": record.source_row_number,
                    "entity_type": record.entity_type,
                    "values": _json_values(record.values),
                }
                for record in records
            ],
        }
        canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        envelope = {
            "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "payload": payload,
        }
        destination = self._path(import_job_id)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=self.base_directory,
            prefix=f"{import_job_id}-",
            suffix=".tmp",
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(envelope, handle, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            os.replace(temporary_name, destination)
        finally:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)

    def load(
        self,
        *,
        import_job_id: int,
        import_type: str,
        source_file_hash: str,
    ) -> list[dict[str, Any]]:
        try:
            envelope = json.loads(self._path(import_job_id).read_text(encoding="utf-8"))
            payload = envelope["payload"]
            canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
            if not hmac.compare_digest(digest, envelope["digest"]):
                raise StagedImportError("The staged import failed its integrity check")
            if payload["import_job_id"] != import_job_id or payload["import_type"] != import_type:
                raise StagedImportError("The staged import does not match the import job")
            if payload["source_file_hash"] != source_file_hash:
                raise StagedImportError("The staged import source hash does not match")
            return list(payload["records"])
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise StagedImportError("The staged import is unavailable") from error

    def remove(self, import_job_id: int) -> None:
        try:
            self._path(import_job_id).unlink()
        except FileNotFoundError:
            pass

    def _path(self, import_job_id: int) -> Path:
        if import_job_id < 1:
            raise ValueError("import_job_id must be positive")
        return self.base_directory / f"{import_job_id}.json"


class ImportBatchWriter:
    """Write an already validated batch through a Repository inside Service transaction."""

    def __init__(self, data: ImportDataRepository) -> None:
        self.data = data

    def write(
        self,
        *,
        import_type: str,
        staged_records: Iterable[dict[str, Any]],
        import_job_id: int,
        administrator_id: int,
    ) -> int:
        count = 0
        for staged in staged_records:
            values = _restore_values(dict(staged["values"]))
            entity_type = str(staged["entity_type"])
            if import_type == "MASTER_DATA":
                self.data.create_master(entity_type, values)
            elif import_type == "SNAPSHOT":
                self._write_snapshot(values, import_job_id, administrator_id)
            else:
                raise ValidationException("Unsupported import type")
            count += 1
        return count

    def _write_snapshot(self, values: dict[str, Any], import_job_id: int, administrator_id: int) -> None:
        drama_platform_id = int(values["drama_platform_id"])
        state = self.data.get_release_state(drama_platform_id)
        if state is None:
            raise ConflictException("A referenced release no longer exists")
        if (
            state["drama_status"] == "INACTIVE"
            or state["platform_status"] != "ACTIVE"
            or state["release_status"] != "ONLINE"
        ):
            raise ConflictException("A referenced release is no longer eligible for import")
        if self.data.snapshot_exists(
            drama_platform_id=drama_platform_id,
            snapshot_time=values["snapshot_time"],
        ):
            raise ConflictException("A snapshot now exists for the staged release and time")
        self.data.create_initial_snapshot(
            values=values,
            changed_by_user_id=administrator_id,
            import_job_id=import_job_id,
        )


def _json_values(values: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value.isoformat() if isinstance(value, (datetime, date)) else value
        for key, value in values.items()
    }


def _restore_values(values: dict[str, Any]) -> dict[str, Any]:
    if "snapshot_time" in values and isinstance(values["snapshot_time"], str):
        values["snapshot_time"] = datetime.fromisoformat(values["snapshot_time"])
    if "premiere_date" in values and isinstance(values["premiere_date"], str):
        values["premiere_date"] = date.fromisoformat(values["premiere_date"])
    return values
