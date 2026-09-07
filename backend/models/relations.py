"""Association and drama-platform release ORM mappings."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, SMALLINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.common import CreatedUpdatedAtMixin

if TYPE_CHECKING:
    from models.drama import Drama
    from models.master_data import Actor, Company, Director, Platform, Tag
    from models.operation_log import OperationLog
    from models.quality import DataQualityIssue
    from models.snapshot import DramaMetricSnapshot


class DramaActor(CreatedUpdatedAtMixin, Base):
    """One actor's principal participation record in one drama."""

    __tablename__ = "drama_actors"
    __table_args__ = (
        UniqueConstraint("drama_id", "actor_id", name="uq_drama_actors_pair"),
        UniqueConstraint(
            "drama_id", "billing_order", name="uq_drama_actors_billing"
        ),
        CheckConstraint(
            "role_type IN ('LEAD', 'SUPPORTING', 'GUEST', 'OTHER')",
            name="chk_drama_actors_role_type",
        ),
        CheckConstraint(
            "billing_order IS NULL OR billing_order > 0",
            name="chk_drama_actors_billing",
        ),
        CheckConstraint(
            "relation_status IN ('ACTIVE', 'INACTIVE')",
            name="chk_drama_actors_status",
        ),
        Index("idx_drama_actors_actor_status", "actor_id", "relation_status"),
    )

    drama_actor_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    drama_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "dramas.drama_id",
            name="fk_drama_actors_drama",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    actor_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "actors.actor_id",
            name="fk_drama_actors_actor",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    role_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role_type: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'OTHER'")
    )
    billing_order: Mapped[int | None] = mapped_column(
        SMALLINT(unsigned=True), nullable=True
    )
    relation_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'ACTIVE'")
    )

    drama: Mapped["Drama"] = relationship(back_populates="actor_relations")
    actor: Mapped["Actor"] = relationship(back_populates="drama_relations")
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        back_populates="target_drama_actor",
        foreign_keys="OperationLog.target_drama_actor_id",
    )


class DramaDirector(CreatedUpdatedAtMixin, Base):
    """Many-to-many association between dramas and directors."""

    __tablename__ = "drama_directors"
    __table_args__ = (
        UniqueConstraint(
            "drama_id", "director_id", name="uq_drama_directors_pair"
        ),
        CheckConstraint(
            "relation_status IN ('ACTIVE', 'INACTIVE')",
            name="chk_drama_directors_status",
        ),
        Index(
            "idx_drama_directors_director_status",
            "director_id",
            "relation_status",
        ),
    )

    drama_director_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    drama_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "dramas.drama_id",
            name="fk_drama_directors_drama",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    director_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "directors.director_id",
            name="fk_drama_directors_director",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    relation_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'ACTIVE'")
    )

    drama: Mapped["Drama"] = relationship(back_populates="director_relations")
    director: Mapped["Director"] = relationship(back_populates="drama_relations")
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        back_populates="target_drama_director",
        foreign_keys="OperationLog.target_drama_director_id",
    )


class DramaCompany(CreatedUpdatedAtMixin, Base):
    """Typed company participation in a drama."""

    __tablename__ = "drama_companies"
    __table_args__ = (
        UniqueConstraint(
            "drama_id",
            "company_id",
            "relation_type",
            name="uq_drama_companies_role",
        ),
        CheckConstraint(
            "relation_type IN ('PRODUCER', 'PRODUCTION', 'DISTRIBUTOR', "
            "'CO_PRODUCTION', 'OTHER')",
            name="chk_drama_companies_type",
        ),
        CheckConstraint(
            "relation_status IN ('ACTIVE', 'INACTIVE')",
            name="chk_drama_companies_status",
        ),
        Index(
            "idx_drama_companies_company_type_status",
            "company_id",
            "relation_type",
            "relation_status",
        ),
    )

    drama_company_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    drama_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "dramas.drama_id",
            name="fk_drama_companies_drama",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    company_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "companies.company_id",
            name="fk_drama_companies_company",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    relation_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'ACTIVE'")
    )

    drama: Mapped["Drama"] = relationship(back_populates="company_relations")
    company: Mapped["Company"] = relationship(back_populates="drama_relations")
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        back_populates="target_drama_company",
        foreign_keys="OperationLog.target_drama_company_id",
    )


class DramaTag(CreatedUpdatedAtMixin, Base):
    """Many-to-many association between dramas and flat tags."""

    __tablename__ = "drama_tags"
    __table_args__ = (
        UniqueConstraint("drama_id", "tag_id", name="uq_drama_tags_pair"),
        CheckConstraint(
            "relation_status IN ('ACTIVE', 'INACTIVE')",
            name="chk_drama_tags_status",
        ),
        Index("idx_drama_tags_tag_status", "tag_id", "relation_status"),
    )

    drama_tag_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    drama_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "dramas.drama_id",
            name="fk_drama_tags_drama",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    tag_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "tags.tag_id",
            name="fk_drama_tags_tag",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    relation_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'ACTIVE'")
    )

    drama: Mapped["Drama"] = relationship(back_populates="tag_relations")
    tag: Mapped["Tag"] = relationship(back_populates="drama_relations")
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        back_populates="target_drama_tag",
        foreign_keys="OperationLog.target_drama_tag_id",
    )


class DramaPlatform(CreatedUpdatedAtMixin, Base):
    """One drama's single V1 release relationship on one platform."""

    __tablename__ = "drama_platforms"
    __table_args__ = (
        UniqueConstraint(
            "drama_id", "platform_id", name="uq_drama_platforms_pair"
        ),
        UniqueConstraint(
            "platform_id",
            "platform_drama_code",
            name="uq_drama_platforms_external_code",
        ),
        CheckConstraint(
            "status IN ('PLANNED', 'ONLINE', 'OFFLINE')",
            name="chk_drama_platforms_status",
        ),
        CheckConstraint(
            "status = 'PLANNED' OR online_at IS NOT NULL",
            name="chk_drama_platforms_online_time",
        ),
        Index(
            "idx_drama_platforms_platform_status_online",
            "platform_id",
            "status",
            "online_at",
        ),
        Index("idx_drama_platforms_drama_status", "drama_id", "status"),
    )

    drama_platform_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    drama_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "dramas.drama_id",
            name="fk_drama_platforms_drama",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    platform_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "platforms.platform_id",
            name="fk_drama_platforms_platform",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    platform_drama_code: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    online_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    page_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'PLANNED'")
    )

    drama: Mapped["Drama"] = relationship(back_populates="platform_relations")
    platform: Mapped["Platform"] = relationship(back_populates="drama_relations")
    snapshots: Mapped[list["DramaMetricSnapshot"]] = relationship(
        back_populates="drama_platform"
    )
    quality_issues: Mapped[list["DataQualityIssue"]] = relationship(
        back_populates="target_drama_platform",
        foreign_keys="DataQualityIssue.target_drama_platform_id",
    )
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        back_populates="target_drama_platform",
        foreign_keys="OperationLog.target_drama_platform_id",
    )
