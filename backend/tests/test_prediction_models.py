"""ORM contract tests for the Phase 3 prediction result schema."""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, inspect
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


def test_prediction_model_registers_with_drama_relationship() -> None:
    configure_mappers()

    assert models.PredictionResult is not None
    assert "prediction_results" in Base.metadata.tables
    assert "drama" in inspect(models.PredictionResult).relationships
    assert "predictions" in inspect(models.Drama).relationships


def test_prediction_columns_match_v010() -> None:
    table = Base.metadata.tables["prediction_results"]

    assert set(table.c.keys()) == {
        "prediction_id",
        "drama_id",
        "metric_type",
        "prediction_date",
        "target_date",
        "predicted_value",
        "algorithm_version",
        "analysis_as_of",
        "created_at",
        "updated_at",
    }
    assert isinstance(table.c.prediction_id.type, BIGINT)
    assert table.c.prediction_id.type.unsigned
    assert table.c.prediction_id.primary_key
    assert table.c.prediction_id.autoincrement is True
    assert isinstance(table.c.predicted_value.type, DECIMAL)
    assert (table.c.predicted_value.type.precision, table.c.predicted_value.type.scale) == (
        20,
        2,
    )
    assert isinstance(table.c.analysis_as_of.type, DATETIME)
    assert table.c.analysis_as_of.type.fsp == 6
    assert {
        "scope_type",
        "scope_id",
        "confidence",
        "actual_value",
        "prediction_error",
        "input_window",
        "predicted_increment",
    }.isdisjoint(table.c.keys())


def test_prediction_constraints_and_indexes_match_v010() -> None:
    table = Base.metadata.tables["prediction_results"]

    assert _named_constraints("prediction_results", UniqueConstraint) == {
        "uq_prediction_results_identity"
    }
    unique = next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_prediction_results_identity"
    )
    assert tuple(unique.columns.keys()) == (
        "drama_id",
        "metric_type",
        "target_date",
        "algorithm_version",
    )
    assert _named_constraints("prediction_results", CheckConstraint) == {
        "chk_prediction_results_algorithm_version",
        "chk_prediction_results_metric_type",
        "chk_prediction_results_predicted_value",
    }

    foreign_key = next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    )
    element = next(iter(foreign_key.elements))
    assert foreign_key.name == "fk_prediction_results_drama"
    assert element.target_fullname == "dramas.drama_id"
    assert element.ondelete == "RESTRICT"
    assert element.onupdate == "RESTRICT"

    assert {
        index.name: tuple(column.name for column in index.columns)
        for index in table.indexes
    } == {
        "idx_prediction_results_drama_metric_target": (
            "drama_id",
            "metric_type",
            "target_date",
        ),
        "idx_prediction_results_metric_target": (
            "metric_type",
            "target_date",
        ),
    }


def test_prediction_table_compiles_for_mysql_8() -> None:
    ddl = str(
        CreateTable(Base.metadata.tables["prediction_results"]).compile(
            dialect=mysql.dialect()
        )
    )

    assert "BIGINT UNSIGNED NOT NULL AUTO_INCREMENT" in ddl
    assert "DECIMAL(20, 2) NOT NULL" in ddl
    assert "DATETIME(6) NOT NULL" in ddl
    assert "FOREIGN KEY(drama_id) REFERENCES dramas (drama_id)" in ddl
    assert "ON DELETE RESTRICT ON UPDATE RESTRICT" in ddl
    assert "CONSTRAINT uq_prediction_results_identity UNIQUE" in ddl
