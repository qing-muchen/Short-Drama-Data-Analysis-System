"""Actor, director, company, platform, and tag ORM mappings."""

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.common import CreatedUpdatedAtMixin

if TYPE_CHECKING:
    from models.operation_log import OperationLog
    from models.relations import DramaActor, DramaCompany, DramaDirector, DramaPlatform, DramaTag


class Actor(CreatedUpdatedAtMixin, Base):
    """Actor master data; names are not assumed globally unique."""

    __tablename__ = "actors"
    __table_args__ = (
        CheckConstraint(
            "CHAR_LENGTH(TRIM(actor_name)) > 0",
            name="chk_actors_name_nonempty",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="chk_actors_status",
        ),
        Index("idx_actors_name_status", "actor_name", "status"),
    )

    actor_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    actor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    profile_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'ACTIVE'")
    )

    drama_relations: Mapped[list["DramaActor"]] = relationship(back_populates="actor")
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        back_populates="target_actor",
        foreign_keys="OperationLog.target_actor_id",
    )


class Director(CreatedUpdatedAtMixin, Base):
    """Director master data; names are not assumed globally unique."""

    __tablename__ = "directors"
    __table_args__ = (
        CheckConstraint(
            "CHAR_LENGTH(TRIM(director_name)) > 0",
            name="chk_directors_name_nonempty",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="chk_directors_status",
        ),
        Index("idx_directors_name_status", "director_name", "status"),
    )

    director_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    director_name: Mapped[str] = mapped_column(String(100), nullable=False)
    profile_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'ACTIVE'")
    )

    drama_relations: Mapped[list["DramaDirector"]] = relationship(
        back_populates="director"
    )
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        back_populates="target_director",
        foreign_keys="OperationLog.target_director_id",
    )


class Company(CreatedUpdatedAtMixin, Base):
    """Company master data."""

    __tablename__ = "companies"
    __table_args__ = (
        CheckConstraint(
            "CHAR_LENGTH(TRIM(company_name)) > 0",
            name="chk_companies_name_nonempty",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="chk_companies_status",
        ),
        Index("idx_companies_name_status", "company_name", "status"),
    )

    company_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'ACTIVE'")
    )

    drama_relations: Mapped[list["DramaCompany"]] = relationship(
        back_populates="company"
    )
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        back_populates="target_company",
        foreign_keys="OperationLog.target_company_id",
    )


class Platform(CreatedUpdatedAtMixin, Base):
    """Distribution platform master data."""

    __tablename__ = "platforms"
    __table_args__ = (
        UniqueConstraint("platform_name", name="uq_platforms_name"),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(platform_name)) > 0",
            name="chk_platforms_name_nonempty",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="chk_platforms_status",
        ),
        Index("idx_platforms_status", "status"),
    )

    platform_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    platform_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'ACTIVE'")
    )

    drama_relations: Mapped[list["DramaPlatform"]] = relationship(
        back_populates="platform"
    )
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        back_populates="target_platform",
        foreign_keys="OperationLog.target_platform_id",
    )


class Tag(CreatedUpdatedAtMixin, Base):
    """Flat tag master data."""

    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("tag_name", name="uq_tags_name"),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(tag_name)) > 0",
            name="chk_tags_name_nonempty",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'INACTIVE')",
            name="chk_tags_status",
        ),
        Index("idx_tags_status", "status"),
    )

    tag_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    tag_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'ACTIVE'")
    )

    drama_relations: Mapped[list["DramaTag"]] = relationship(back_populates="tag")
    operation_logs: Mapped[list["OperationLog"]] = relationship(
        back_populates="target_tag",
        foreign_keys="OperationLog.target_tag_id",
    )
