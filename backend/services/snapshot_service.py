"""Snapshot Service dependency boundary; revision flows are not implemented."""

from sqlalchemy.orm import Session

from repositories.snapshot_repository import SnapshotRepository
from services.base import BaseService


class SnapshotService(BaseService):
    """Future entry point for slot, revision, correction, and VOID rules."""

    def __init__(self, session: Session, snapshots: SnapshotRepository) -> None:
        super().__init__(session, snapshots)
        self.snapshots = snapshots
