"""Metadata and constraint tests for the V012 operation action schema."""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import mysql

import models


def test_operation_action_tables_are_registered() -> None:
    assert {
        "operation_actions",
        "operation_action_sources",
        "operation_action_history",
    }.issubset(models.OperationAction.metadata.tables)


def test_operation_action_relationships_are_explicit() -> None:
    assert models.OperationAction.drama.property.back_populates == "operation_actions"
    assert models.OperationAction.sources.property.back_populates == "action"
    assert models.OperationAction.history.property.back_populates == "action"
    assert models.OperationActionSource.action.property.back_populates == "sources"
    assert models.OperationActionHistory.action.property.back_populates == "history"


def test_operation_action_constraints_and_indexes() -> None:
    for model in (
        models.OperationAction,
        models.OperationActionSource,
        models.OperationActionHistory,
    ):
        table = model.__table__
        assert len(table.primary_key.columns) == 1
        assert any(isinstance(item, ForeignKeyConstraint) for item in table.constraints)
        assert any(isinstance(item, CheckConstraint) for item in table.constraints)
        assert any(isinstance(item, Index) for item in table.indexes)

    source_table = models.OperationActionSource.__table__
    assert any(
        isinstance(item, UniqueConstraint)
        and item.name == "uq_operation_action_sources_identity"
        for item in source_table.constraints
    )


def test_operation_action_mysql_ddl_compiles() -> None:
    for model in (
        models.OperationAction,
        models.OperationActionSource,
        models.OperationActionHistory,
    ):
        ddl = str(CreateTable(model.__table__).compile(dialect=mysql.dialect()))
        assert f"CREATE TABLE {model.__tablename__}" in ddl
