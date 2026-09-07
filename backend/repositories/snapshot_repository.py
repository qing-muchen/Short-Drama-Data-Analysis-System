"""Observation-slot persistence queries without analytics calculations."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.sql import Select

from models.snapshot import DramaMetricSnapshot
from repositories.base import BaseRepository, Page


class SnapshotRepository(BaseRepository[DramaMetricSnapshot]):
    """Database access for stable snapshot observation slots."""

    model = DramaMetricSnapshot

    def get_by_platform_and_time(
        self,
        *,
        drama_platform_id: int,
        snapshot_time: datetime,
    ) -> DramaMetricSnapshot | None:
        statement = select(DramaMetricSnapshot).where(
            DramaMetricSnapshot.drama_platform_id == drama_platform_id,
            DramaMetricSnapshot.snapshot_time == snapshot_time,
        )
        return self.session.scalar(statement)

    def list_by_drama_platform(
        self,
        *,
        drama_platform_id: int,
        page: int,
        page_size: int,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> Page[DramaMetricSnapshot]:
        statement = select(DramaMetricSnapshot).where(
            DramaMetricSnapshot.drama_platform_id == drama_platform_id
        )
        statement = self._apply_time_range(
            statement,
            start_time=start_time,
            end_time=end_time,
        )
        statement = statement.order_by(
            DramaMetricSnapshot.snapshot_time.desc(),
            DramaMetricSnapshot.snapshot_id.desc(),
        )
        return self.paginate(statement, page=page, page_size=page_size)

    def list_by_time_range(
        self,
        *,
        start_time: datetime,
        end_time: datetime,
        page: int,
        page_size: int,
    ) -> Page[DramaMetricSnapshot]:
        statement = self._apply_time_range(
            select(DramaMetricSnapshot),
            start_time=start_time,
            end_time=end_time,
        ).order_by(
            DramaMetricSnapshot.snapshot_time.desc(),
            DramaMetricSnapshot.snapshot_id.desc(),
        )
        return self.paginate(statement, page=page, page_size=page_size)

    @staticmethod
    def _apply_time_range(
        statement: Select[tuple[DramaMetricSnapshot]],
        *,
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> Select[tuple[DramaMetricSnapshot]]:
        if start_time is not None:
            statement = statement.where(
                DramaMetricSnapshot.snapshot_time >= start_time
            )
        if end_time is not None:
            statement = statement.where(DramaMetricSnapshot.snapshot_time <= end_time)
        return statement
