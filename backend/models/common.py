"""Shared SQLAlchemy column mixins for the frozen MySQL schema."""

from datetime import datetime

from sqlalchemy import FetchedValue, text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column


class CreatedUpdatedAtMixin:
    """Map the UTC audit timestamps shared by mutable business tables."""

    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(6)"),
        server_onupdate=FetchedValue(),
    )
