"""Drama ORM mapping."""

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT, INTEGER, SMALLINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.common import CreatedUpdatedAtMixin

if TYPE_CHECKING:
    from models.operation_log import OperationLog
    from models.quality import DataQualityIssue
    from models.relations import (
        DramaActor,
        DramaCompany,
        DramaDirector,
        DramaPlatform,
        DramaTag,
    )


class Drama(CreatedUpdatedAtMixin, Base):
    """Short-drama business entity without denormalized relations or metrics."""

    __tablename__ = "dramas"
    __table_args__ = (
        UniqueConstraint("drama_code", name="uq_dramas_code"),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(drama_code)) > 0",
            name="chk_dramas_code_nonempty",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(drama_name)) > 0",
            name="chk_dramas_name_nonempty",
        ),
        CheckConstraint(
            "episode_count IS NULL OR episode_count > 0",
            name="chk_dramas_episode_count",
        ),
        CheckConstraint(
            "episode_duration_seconds IS NULL OR episode_duration_seconds > 0",
            name="chk_dramas_episode_duration",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'SERIALIZING', 'COMPLETED', 'INACTIVE')",
            name="chk_dramas_status",
        ),
        Index("idx_dramas_status_premiere", "status", "premiere_date"),
        Index("idx_dramas_name", "drama_name"),
    )

    drama_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    drama_code: Mapped[str] = mapped_column(String(32), nullable=False)
    drama_name: Mapped[str] = mapped_column(String(200), nullable=False)
    synopsis: Mapped[str | None] = mapped_column(Text, nullable=True)
    episode_count: Mapped[int | None] = mapped_column(
        SMALLINT(unsigned=True), nullable=True
    )
    episode_duration_seconds: Mapped[int | None] = mapped_column(
        INTEGER(unsigned=True), nullable=True
    )
    premiere_date: Mapped[date | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'DRAFT'")
    )

    actor_relations: Mapped[list["DramaActor"]] = relationship(
        back_populates="drama"
    )
    director_relations: Mapped[list["DramaDirector"]] = relationship(
        back_populates="drama"
    )
    company_relations: Mapped[list["DramaCompany"]] = relationship(
        back_populates="drama"
    )
    tag_relations: Mapped[list["DramaTag"]] = relationship(back_populates="drama")
    platform_relations: Mapped[list["DramaPlatform"]] = relationship(
        back_populates="drama"
    )
    quality_issues: Mapped[list["DataQualityIssue"]] = relationship(
        back_populates="target_drama",
        foreign_keys="DataQualityIssue.target_drama_id",
    )
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        back_populates="target_drama",
        foreign_keys="OperationLog.target_drama_id",
    )
