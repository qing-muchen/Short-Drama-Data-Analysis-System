"""ORM contract tests for the Phase 4 anomaly finding schema."""

from sqlalchemy import CHAR, CheckConstraint, ForeignKeyConstraint, UniqueConstraint, inspect
from sqlalchemy.dialects import mysql
from sqlalchemy.dialects.mysql import BIGINT, DATETIME, DECIMAL
from sqlalchemy.orm import configure_mappers
from sqlalchemy.schema import CreateTable

import models
from database.base import Base


def _named_constraints(table_name: str, kind: type[object]) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, kind) and constraint.name is not None
    }


def test_anomaly_model_registers_with_drama_relationship() -> None:
    """The anomaly model is importable and linked to Drama without a DB."""

    configure_mappers()

    assert models.DataAnomalyRecord is not None
    assert "data_anomaly_records" in Base.metadata.tables
    assert "drama" in inspect(models.DataAnomalyRecord).relationships
    assert "anomaly_records" in inspect(models.Drama).relationships


def test_anomaly_columns_match_v011() -> None:
    """V011 columns preserve the frozen finding/result separation."""

    table = Base.metadata.tables["data_anomaly_records"]

    assert set(table.c.keys()) == {
        "anomaly_id",
        "drama_id",
        "metric_type",
        "anomaly_type",
        "severity",
        "status",
        "analysis_as_of",
        "detected_at",
        "algorithm_version",
        "baseline_value",
        "actual_value",
        "deviation_value",
        "evidence_summary",
        "created_at",
        "updated_at",
    }
    assert isinstance(table.c.anomaly_id.type, BIGINT)
    assert table.c.anomaly_id.type.unsigned
    assert table.c.anomaly_id.primary_key
    assert table.c.anomaly_id.autoincrement is True
    assert isinstance(table.c.severity.type, CHAR)
    assert table.c.severity.type.length == 1
    for column_name in ("baseline_value", "actual_value", "deviation_value"):
        column_type = table.c[column_name].type
        assert isinstance(column_type, DECIMAL)
        assert (column_type.precision, column_type.scale) == (18, 4)
    for column_name in ("analysis_as_of", "detected_at"):
        column_type = table.c[column_name].type
        assert isinstance(column_type, DATETIME)
        assert column_type.fsp == 6
    assert table.c.evidence_summary.nullable is False
    assert {"drama_name", "platform_name"}.isdisjoint(table.c.keys())


def test_anomaly_constraints_and_indexes_match_v011() -> None:
    """V011 identity, dictionaries, FK and query indexes are explicit."""

    table = Base.metadata.tables["data_anomaly_records"]

    assert _named_constraints("data_anomaly_records", UniqueConstraint) == {
        "uq_data_anomaly_records_identity"
    }
    unique = next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_data_anomaly_records_identity"
    )
    assert tuple(unique.columns.keys()) == (
        "drama_id",
        "metric_type",
        "anomaly_type",
        "analysis_as_of",
        "algorithm_version",
    )
    assert _named_constraints("data_anomaly_records", CheckConstraint) == {
        "chk_data_anomaly_records_algorithm_version",
        "chk_data_anomaly_records_anomaly_type",
        "chk_data_anomaly_records_metric_type",
        "chk_data_anomaly_records_severity",
        "chk_data_anomaly_records_status",
    }

    foreign_keys = {
        constraint.name: next(iter(constraint.elements))
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert set(foreign_keys) == {"fk_data_anomaly_records_drama"}
    element = foreign_keys["fk_data_anomaly_records_drama"]
    assert element.target_fullname == "dramas.drama_id"
    assert element.ondelete == "RESTRICT"
    assert element.onupdate == "RESTRICT"

    assert {
        index.name: tuple(column.name for column in index.columns)
        for index in table.indexes
    } == {
        "idx_anomaly_query": (
            "analysis_as_of",
            "status",
            "severity",
            "metric_type",
        ),
        "idx_anomaly_trend": ("drama_id", "analysis_as_of"),
    }


def test_anomaly_table_compiles_for_mysql_8() -> None:
    """The ORM emits MySQL-compatible V011 DDL fragments."""

    ddl = str(
        CreateTable(Base.metadata.tables["data_anomaly_records"]).compile(
            dialect=mysql.dialect()
        )
    )

    assert "BIGINT UNSIGNED NOT NULL AUTO_INCREMENT" in ddl
    assert "CHAR(1) NOT NULL" in ddl
    assert "DECIMAL(18, 4)" in ddl
    assert "DATETIME(6) NOT NULL" in ddl
    assert "FOREIGN KEY(drama_id) REFERENCES dramas (drama_id)" in ddl
    assert "ON DELETE RESTRICT ON UPDATE RESTRICT" in ddl
    assert "CONSTRAINT uq_data_anomaly_records_identity UNIQUE" in ddl
    assert "CONSTRAINT chk_data_anomaly_records_status CHECK" in ddl
