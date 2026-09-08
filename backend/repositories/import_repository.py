"""Persistence operations for staged imports and their target records."""

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from models.drama import Drama
from models.import_job import ImportError, ImportJob
from models.master_data import Actor, Company, Director, Platform, Tag
from models.operation_log import OperationLog
from models.relations import DramaPlatform
from models.snapshot import DramaMetricSnapshot, DramaMetricSnapshotRevision
from repositories.base import BaseRepository, Page


class ImportJobRepository(BaseRepository[ImportJob]):
    model = ImportJob

    def claim_ready(self, import_job_id: int) -> bool:
        """Atomically claim one READY job for confirmation without committing."""

        statement = (
            update(ImportJob)
            .where(
                ImportJob.import_job_id == import_job_id,
                ImportJob.status == "READY",
            )
            .values(status="IMPORTING")
            .execution_options(synchronize_session="fetch")
        )
        result = self.session.execute(statement)
        return result.rowcount == 1


class ImportErrorRepository(BaseRepository[ImportError]):
    model = ImportError

    def list_by_job(self, import_job_id: int, *, page: int, page_size: int) -> Page[ImportError]:
        statement = (
            select(ImportError)
            .where(ImportError.import_job_id == import_job_id)
            .order_by(ImportError.source_row_number.asc(), ImportError.import_error_id.asc())
        )
        return self.paginate(statement, page=page, page_size=page_size)

    def create_many(self, values: Sequence[Mapping[str, Any]]) -> list[ImportError]:
        entities = [ImportError(**dict(item)) for item in values]
        self.session.add_all(entities)
        self.session.flush()
        return entities


class ImportDataRepository:
    """Database lookups and writes used only by ImportService."""

    _MASTER_MODELS = {
        "DRAMA": Drama,
        "ACTOR": Actor,
        "DIRECTOR": Director,
        "COMPANY": Company,
        "PLATFORM": Platform,
        "TAG": Tag,
    }

    def __init__(self, session: Session) -> None:
        self.session = session

    def master_uniqueness_context(self) -> tuple[set[str], set[str], set[str]]:
        drama_codes = set(self.session.scalars(select(Drama.drama_code)).all())
        platform_names = set(self.session.scalars(select(Platform.platform_name)).all())
        tag_names = set(self.session.scalars(select(Tag.tag_name)).all())
        return drama_codes, platform_names, tag_names

    def snapshot_release_context(
        self,
        *,
        drama_codes: Iterable[str],
        platform_names: Iterable[str],
    ) -> dict[tuple[str, str], dict[str, Any]]:
        codes = sorted(set(drama_codes))
        names = sorted(set(platform_names))
        if not codes or not names:
            return {}
        statement = (
            select(
                Drama.drama_code,
                Drama.status,
                Platform.platform_name,
                Platform.status,
                DramaPlatform.drama_platform_id,
                DramaPlatform.status,
            )
            .join(DramaPlatform, DramaPlatform.drama_id == Drama.drama_id)
            .join(Platform, Platform.platform_id == DramaPlatform.platform_id)
            .where(Drama.drama_code.in_(codes), Platform.platform_name.in_(names))
        )
        rows = self.session.execute(statement).all()
        return {
            (str(row[0]).strip().casefold(), str(row[2]).strip().casefold()): {
                "drama_status": row[1],
                "platform_status": row[3],
                "drama_platform_id": row[4],
                "release_status": row[5],
            }
            for row in rows
        }

    def existing_snapshot_keys(
        self,
        *,
        drama_platform_ids: Iterable[int],
        start_time: datetime,
        end_time: datetime,
    ) -> set[tuple[int, datetime]]:
        identifiers = sorted(set(drama_platform_ids))
        if not identifiers:
            return set()
        statement = select(
            DramaMetricSnapshot.drama_platform_id,
            DramaMetricSnapshot.snapshot_time,
        ).where(
            DramaMetricSnapshot.drama_platform_id.in_(identifiers),
            DramaMetricSnapshot.snapshot_time >= start_time,
            DramaMetricSnapshot.snapshot_time <= end_time,
        )
        return {(int(row[0]), row[1]) for row in self.session.execute(statement).all()}

    def get_release_state(self, drama_platform_id: int) -> dict[str, Any] | None:
        statement = (
            select(Drama.status, Platform.status, DramaPlatform.status)
            .select_from(DramaPlatform)
            .join(Drama, Drama.drama_id == DramaPlatform.drama_id)
            .join(Platform, Platform.platform_id == DramaPlatform.platform_id)
            .where(DramaPlatform.drama_platform_id == drama_platform_id)
        )
        row = self.session.execute(statement).one_or_none()
        if row is None:
            return None
        return {"drama_status": row[0], "platform_status": row[1], "release_status": row[2]}

    def snapshot_exists(self, *, drama_platform_id: int, snapshot_time: datetime) -> bool:
        statement = select(DramaMetricSnapshot.snapshot_id).where(
            DramaMetricSnapshot.drama_platform_id == drama_platform_id,
            DramaMetricSnapshot.snapshot_time == snapshot_time,
        )
        return self.session.scalar(statement) is not None

    def create_master(self, entity_type: str, values: Mapping[str, Any]) -> Any:
        model = self._MASTER_MODELS[entity_type]
        entity = model(**dict(values))
        self.session.add(entity)
        self.session.flush()
        return entity

    def create_initial_snapshot(
        self,
        *,
        values: Mapping[str, Any],
        changed_by_user_id: int,
        import_job_id: int,
    ) -> DramaMetricSnapshot:
        slot = DramaMetricSnapshot(
            drama_platform_id=values["drama_platform_id"],
            snapshot_time=values["snapshot_time"],
            source_import_job_id=import_job_id,
        )
        self.session.add(slot)
        self.session.flush()
        revision = DramaMetricSnapshotRevision(
            snapshot_id=slot.snapshot_id,
            version_no=1,
            previous_revision_id=None,
            revision_action="INITIAL",
            play_count=values["play_count"],
            like_count=values["like_count"],
            comment_count=values["comment_count"],
            favorite_count=values["favorite_count"],
            share_count=values["share_count"],
            ranking=values.get("ranking"),
            change_reason=None,
            changed_by_user_id=changed_by_user_id,
        )
        self.session.add(revision)
        self.session.flush()
        slot.current_revision_id = revision.snapshot_revision_id
        self.session.flush()
        return slot


class OperationLogRepository(BaseRepository[OperationLog]):
    model = OperationLog
