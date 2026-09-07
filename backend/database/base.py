"""Declarative base shared by future schema-faithful ORM mappings."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for models added only by later authorized tasks."""
