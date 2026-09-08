"""Read-only persistence queries feeding the Analytics Service."""

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from sqlalchemy import exists, or_, select

from models.drama import Drama
from models.master_data import Platform
from models.quality import DataQualityIssue
from models.relations import DramaPlatform, DramaTag
from models.snapshot import DramaMetricSnapshot, DramaMetricSnapshotRevision
from repositories.base import BaseRepository


@dataclass(frozen=True, slots=True)
class AnalyticsRecord:
    drama_id: int
    drama_code: str
    drama_name: str
    drama_status: str
    drama_platform_id: int
    drama_platform_status: str
    platform_id: int
    platform_status: str
    snapshot_id: int
    snapshot_revision_id: int
    snapshot_time: datetime
    revision_action: str
    play_count: int | None
    like_count: int | None
    comment_count: int | None
    favorite_count: int | None
    share_count: int | None
    ranking: int | None
    tag_ids: tuple[int, ...]
    warning_count: int
    error_count: int


class AnalyticsRepository(BaseRepository[DramaMetricSnapshot]):
    """Return current-revision facts and governance metadata without scoring."""

    model = DramaMetricSnapshot

    def list_snapshot_records(
        self,
        *,
        analysis_as_of: datetime,
        platform_ids: Sequence[int] = (),
        tag_ids: Sequence[int] = (),
    ) -> list[AnalyticsRecord]:
        statement = (
            select(
                DramaMetricSnapshot,
                DramaMetricSnapshotRevision,
                DramaPlatform,
                Drama,
                Platform,
            )
            .join(
                DramaMetricSnapshotRevision,
                DramaMetricSnapshot.current_revision_id
                == DramaMetricSnapshotRevision.snapshot_revision_id,
            )
            .join(
                DramaPlatform,
                DramaMetricSnapshot.drama_platform_id
                == DramaPlatform.drama_platform_id,
            )
            .join(Drama, DramaPlatform.drama_id == Drama.drama_id)
            .join(Platform, DramaPlatform.platform_id == Platform.platform_id)
            .where(DramaMetricSnapshot.snapshot_time <= analysis_as_of)
            .order_by(
                DramaPlatform.drama_platform_id,
                DramaMetricSnapshot.snapshot_time,
                DramaMetricSnapshot.snapshot_id,
            )
        )
        if platform_ids:
            statement = statement.where(DramaPlatform.platform_id.in_(platform_ids))
        if tag_ids:
            statement = statement.where(
                exists(
                    select(1).where(
                        DramaTag.drama_id == Drama.drama_id,
                        DramaTag.tag_id.in_(tag_ids),
                        DramaTag.relation_status == "ACTIVE",
                    )
                )
            )

        rows = self.session.execute(statement).all()
        if not rows:
            return []

        drama_ids = {row.Drama.drama_id for row in rows}
        drama_platform_ids = {
            row.DramaPlatform.drama_platform_id for row in rows
        }
        revision_ids = {
            row.DramaMetricSnapshotRevision.snapshot_revision_id for row in rows
        }

        tag_rows = self.session.execute(
            select(DramaTag.drama_id, DramaTag.tag_id).where(
                DramaTag.drama_id.in_(drama_ids),
                DramaTag.relation_status == "ACTIVE",
            )
        ).all()
        tags_by_drama: dict[int, set[int]] = {}
        for drama_id, tag_id in tag_rows:
            tags_by_drama.setdefault(drama_id, set()).add(tag_id)

        issues = self.session.scalars(
            select(DataQualityIssue).where(
                DataQualityIssue.status.in_(("OPEN", "CONFIRMED")),
                or_(
                    DataQualityIssue.target_drama_id.in_(drama_ids),
                    DataQualityIssue.target_drama_platform_id.in_(
                        drama_platform_ids
                    ),
                    DataQualityIssue.target_snapshot_revision_id.in_(revision_ids),
                ),
            )
        ).all()

        issues_by_drama: dict[int, list[DataQualityIssue]] = {}
        issues_by_platform: dict[int, list[DataQualityIssue]] = {}
        issues_by_revision: dict[int, list[DataQualityIssue]] = {}
        for issue in issues:
            if issue.target_drama_id is not None:
                issues_by_drama.setdefault(issue.target_drama_id, []).append(issue)
            if issue.target_drama_platform_id is not None:
                issues_by_platform.setdefault(
                    issue.target_drama_platform_id, []
                ).append(issue)
            if issue.target_snapshot_revision_id is not None:
                issues_by_revision.setdefault(
                    issue.target_snapshot_revision_id, []
                ).append(issue)

        records: list[AnalyticsRecord] = []
        for row in rows:
            slot = row.DramaMetricSnapshot
            revision = row.DramaMetricSnapshotRevision
            release = row.DramaPlatform
            drama = row.Drama
            platform = row.Platform
            relevant_issues = [
                *issues_by_drama.get(drama.drama_id, ()),
                *issues_by_platform.get(release.drama_platform_id, ()),
                *issues_by_revision.get(revision.snapshot_revision_id, ()),
            ]
            records.append(
                AnalyticsRecord(
                    drama_id=drama.drama_id,
                    drama_code=drama.drama_code,
                    drama_name=drama.drama_name,
                    drama_status=drama.status,
                    drama_platform_id=release.drama_platform_id,
                    drama_platform_status=release.status,
                    platform_id=platform.platform_id,
                    platform_status=platform.status,
                    snapshot_id=slot.snapshot_id,
                    snapshot_revision_id=revision.snapshot_revision_id,
                    snapshot_time=slot.snapshot_time,
                    revision_action=revision.revision_action,
                    play_count=revision.play_count,
                    like_count=revision.like_count,
                    comment_count=revision.comment_count,
                    favorite_count=revision.favorite_count,
                    share_count=revision.share_count,
                    ranking=revision.ranking,
                    tag_ids=tuple(sorted(tags_by_drama.get(drama.drama_id, ()))),
                    warning_count=sum(
                        issue.severity == "WARNING" for issue in relevant_issues
                    ),
                    error_count=sum(
                        issue.severity == "ERROR" for issue in relevant_issues
                    ),
                )
            )
        return records
