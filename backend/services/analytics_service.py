"""Analytics Service wiring only; no metric or insight algorithm is implemented."""

from sqlalchemy.orm import Session

from repositories.drama_repository import DramaRepository
from repositories.platform_repository import PlatformRepository
from repositories.snapshot_repository import SnapshotRepository
from repositories.tag_repository import TagRepository
from services.base import BaseService


class AnalyticsService(BaseService):
    """Future entry point for versioned analysis over Repository data."""

    def __init__(
        self,
        session: Session,
        dramas: DramaRepository,
        platforms: PlatformRepository,
        tags: TagRepository,
        snapshots: SnapshotRepository,
    ) -> None:
        super().__init__(session, dramas, platforms, tags, snapshots)
        self.dramas = dramas
        self.platforms = platforms
        self.tags = tags
        self.snapshots = snapshots
