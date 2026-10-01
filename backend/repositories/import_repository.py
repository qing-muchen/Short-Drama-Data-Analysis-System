"""Persistence operations for staged imports and their target records."""

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from models.drama import Drama
from models.import_job import ImportError, ImportJob
from models.import_batch import ImportBatch
from models.master_data import Actor, Company, Director, Platform, Tag
from models.operation_log import OperationLog
from models.relations import DramaPlatform, DramaTag
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

    def list_by_batch(self, import_batch_id: int) -> list[ImportJob]:
        statement = (
            select(ImportJob)
            .where(ImportJob.import_batch_id == import_batch_id)
            .order_by(ImportJob.batch_sequence.asc())
        )
        return list(self.session.scalars(statement).all())

    def get_batch_file(self, import_batch_id: int, batch_file_type: str) -> ImportJob | None:
        statement = select(ImportJob).where(
            ImportJob.import_batch_id == import_batch_id,
            ImportJob.batch_file_type == batch_file_type,
        )
        return self.session.scalar(statement)


class ImportBatchRepository(BaseRepository[ImportBatch]):
    model = ImportBatch

    def get_by_id(self, entity_id: int) -> ImportBatch | None:
        statement = (
            select(ImportBatch)
            .where(ImportBatch.import_batch_id == entity_id)
            .options(selectinload(ImportBatch.files))
            .execution_options(populate_existing=True)
        )
        return self.session.scalar(statement)

    def get_by_code(self, batch_code: str) -> ImportBatch | None:
        return self.session.scalar(
            select(ImportBatch).where(ImportBatch.batch_code == batch_code)
        )

    def claim_status(self, import_batch_id: int, expected: str, next_status: str) -> bool:
        statement = (
            update(ImportBatch)
            .where(
                ImportBatch.import_batch_id == import_batch_id,
                ImportBatch.status == expected,
            )
            .values(status=next_status)
            .execution_options(synchronize_session="fetch")
        )
        return self.session.execute(statement).rowcount == 1


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
    _MASTER_PRIMARY_KEYS = {
        "DRAMA": Drama.drama_id,
        "ACTOR": Actor.actor_id,
        "DIRECTOR": Director.director_id,
        "COMPANY": Company.company_id,
        "PLATFORM": Platform.platform_id,
        "TAG": Tag.tag_id,
    }

    def __init__(self, session: Session) -> None:
        self.session = session

    def master_uniqueness_context(self) -> tuple[set[str], set[str], set[str]]:
        drama_codes = set(self.session.scalars(select(Drama.drama_code)).all())
        platform_names = set(self.session.scalars(select(Platform.platform_name)).all())
        tag_names = set(self.session.scalars(select(Tag.tag_name)).all())
        return drama_codes, platform_names, tag_names

    def existing_master_primary_keys(
        self,
        primary_keys: Mapping[str, Iterable[int]],
    ) -> dict[str, set[int]]:
        """Return only requested primary keys that already exist in each master table."""

        existing: dict[str, set[int]] = {}
        for entity_type, column in self._MASTER_PRIMARY_KEYS.items():
            requested = sorted(set(primary_keys.get(entity_type, ())))
            existing[entity_type] = (
                {
                    int(value)
                    for value in self.session.scalars(
                        select(column).where(column.in_(requested))
                    ).all()
                }
                if requested
                else set()
            )
        return existing

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

    def batch_reference_context(
        self,
        *,
        drama_codes: Iterable[str],
        platform_names: Iterable[str],
        tag_names: Iterable[str],
    ) -> dict[str, Any]:
        codes = sorted(set(drama_codes))
        platforms = sorted(set(platform_names))
        tags = sorted(set(tag_names))
        drama_rows = self.session.execute(
            select(Drama.drama_id, Drama.drama_code, Drama.status).where(
                Drama.drama_code.in_(codes)
            )
        ).all() if codes else []
        platform_rows = self.session.execute(
            select(Platform.platform_id, Platform.platform_name, Platform.status).where(
                Platform.platform_name.in_(platforms)
            )
        ).all() if platforms else []
        tag_rows = self.session.execute(
            select(Tag.tag_id, Tag.tag_name, Tag.status).where(Tag.tag_name.in_(tags))
        ).all() if tags else []
        drama_map = {str(row[1]).strip().casefold(): {"id": int(row[0]), "status": row[2]} for row in drama_rows}
        platform_map = {str(row[1]).strip().casefold(): {"id": int(row[0]), "status": row[2]} for row in platform_rows}
        tag_map = {str(row[1]).strip().casefold(): {"id": int(row[0]), "status": row[2]} for row in tag_rows}
        drama_ids = [item["id"] for item in drama_map.values()]
        platform_ids = [item["id"] for item in platform_map.values()]
        tag_ids = [item["id"] for item in tag_map.values()]
        tag_pairs = set()
        if drama_ids and tag_ids:
            tag_pairs = {
                (int(row[0]), int(row[1]))
                for row in self.session.execute(
                    select(DramaTag.drama_id, DramaTag.tag_id).where(
                        DramaTag.drama_id.in_(drama_ids), DramaTag.tag_id.in_(tag_ids)
                    )
                ).all()
            }
        platform_pairs = set()
        external_codes = set()
        if drama_ids and platform_ids:
            rows = self.session.execute(
                select(
                    DramaPlatform.drama_id,
                    DramaPlatform.platform_id,
                ).where(
                    DramaPlatform.drama_id.in_(drama_ids),
                    DramaPlatform.platform_id.in_(platform_ids),
                )
            ).all()
            platform_pairs = {(int(row[0]), int(row[1])) for row in rows}
        if platform_ids:
            rows = self.session.execute(
                select(
                    DramaPlatform.platform_id,
                    DramaPlatform.platform_drama_code,
                ).where(DramaPlatform.platform_id.in_(platform_ids))
            ).all()
            external_codes = {
                (int(row[0]), str(row[1]).strip().casefold())
                for row in rows if row[1]
            }
        return {
            "dramas": drama_map,
            "platforms": platform_map,
            "tags": tag_map,
            "drama_tag_pairs": tag_pairs,
            "drama_platform_pairs": platform_pairs,
            "platform_external_codes": external_codes,
        }

    def resolve_drama_ids(self, drama_codes: Iterable[str]) -> dict[str, int]:
        codes = sorted(set(drama_codes))
        if not codes:
            return {}
        return {
            str(code).strip().casefold(): int(identifier)
            for identifier, code in self.session.execute(
                select(Drama.drama_id, Drama.drama_code).where(Drama.drama_code.in_(codes))
            ).all()
        }

    def resolve_platform_ids(self, platform_names: Iterable[str]) -> dict[str, int]:
        names = sorted(set(platform_names))
        if not names:
            return {}
        return {
            str(name).strip().casefold(): int(identifier)
            for identifier, name in self.session.execute(
                select(Platform.platform_id, Platform.platform_name).where(
                    Platform.platform_name.in_(names)
                )
            ).all()
        }

    def resolve_tag_ids(self, tag_names: Iterable[str]) -> dict[str, int]:
        names = sorted(set(tag_names))
        if not names:
            return {}
        return {
            str(name).strip().casefold(): int(identifier)
            for identifier, name in self.session.execute(
                select(Tag.tag_id, Tag.tag_name).where(Tag.tag_name.in_(names))
            ).all()
        }

    def create_drama_tags(self, values: Sequence[Mapping[str, Any]]) -> None:
        self.session.add_all(DramaTag(**dict(item)) for item in values)
        self.session.flush()

    def create_drama_platforms(self, values: Sequence[Mapping[str, Any]]) -> None:
        self.session.add_all(DramaPlatform(**dict(item)) for item in values)
        self.session.flush()

    def create_master(self, entity_type: str, values: Mapping[str, Any]) -> Any:
        model = self._MASTER_MODELS[entity_type]
        entity = model(**dict(values))
        self.session.add(entity)
        self.session.flush()
        return entity

    def create_masters(
        self, records: Sequence[tuple[str, Mapping[str, Any]]]
    ) -> None:
        entities = [
            self._MASTER_MODELS[entity_type](**dict(values))
            for entity_type, values in records
        ]
        self.session.add_all(entities)
        self.session.flush()

    def create_masters(
        self, records: Sequence[tuple[str, Mapping[str, Any]]]
    ) -> None:
        entities = [self._MASTER_MODELS[entity_type](**dict(values)) for entity_type, values in records]
        self.session.add_all(entities)
        self.session.flush()

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

    def create_initial_snapshots(
        self,
        records: Sequence[tuple[Mapping[str, Any], int]],
        *,
        changed_by_user_id: int,
    ) -> None:
        slots = [
            DramaMetricSnapshot(
                drama_platform_id=values["drama_platform_id"],
                snapshot_time=values["snapshot_time"],
                source_import_job_id=import_job_id,
            )
            for values, import_job_id in records
        ]
        self.session.add_all(slots)
        self.session.flush()
        revisions = [
            DramaMetricSnapshotRevision(
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
            for slot, (values, _) in zip(slots, records)
        ]
        self.session.add_all(revisions)
        self.session.flush()
        for slot, revision in zip(slots, revisions):
            slot.current_revision_id = revision.snapshot_revision_id
        self.session.flush()

    def create_initial_snapshots(
        self,
        records: Sequence[tuple[Mapping[str, Any], int]],
        *,
        changed_by_user_id: int,
    ) -> None:
        slots = [
            DramaMetricSnapshot(
                drama_platform_id=values["drama_platform_id"],
                snapshot_time=values["snapshot_time"],
                source_import_job_id=import_job_id,
            )
            for values, import_job_id in records
        ]
        self.session.add_all(slots)
        self.session.flush()
        revisions = [
            DramaMetricSnapshotRevision(
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
            for slot, (values, _) in zip(slots, records, strict=True)
        ]
        self.session.add_all(revisions)
        self.session.flush()
        for slot, revision in zip(slots, revisions, strict=True):
            slot.current_revision_id = revision.snapshot_revision_id
        self.session.flush()


class OperationLogRepository(BaseRepository[OperationLog]):
    model = OperationLog
