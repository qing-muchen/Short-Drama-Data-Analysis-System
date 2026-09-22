"""Metadata and DDL tests for the V013 explanation and lineage schema."""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.dialects import mysql
from sqlalchemy.dialects.mysql import BIGINT, JSON
from sqlalchemy.schema import CreateTable

import models


MODELS = (
    models.AnalysisExplanation,
    models.AnalysisLineageRecord,
    models.MetricDependency,
)


def test_explanation_models_import_and_register_metadata() -> None:
    assert {
        "analysis_explanations",
        "analysis_lineage_records",
        "metric_dependencies",
    }.issubset(models.AnalysisExplanation.metadata.tables)
    assert all(model.__name__ in models.__all__ for model in MODELS)


def test_explanation_fields_and_mysql_types_match_v013() -> None:
    explanation = models.AnalysisExplanation.__table__
    assert set(explanation.c.keys()) == {
        "explanation_id", "entity_type", "entity_id", "module_type", "summary",
        "detail", "algorithm_version", "rule_set_version", "analysis_as_of",
        "created_at",
    }
    assert isinstance(explanation.c.explanation_id.type, BIGINT)
    assert explanation.c.explanation_id.type.unsigned is True
    assert isinstance(explanation.c.detail.type, JSON)
    assert explanation.c.entity_id.nullable is False

    lineage = models.AnalysisLineageRecord.__table__
    assert lineage.c.target_id.nullable is False
    assert lineage.c.source_id.nullable is False
    assert isinstance(lineage.c.target_id.type, BIGINT)
    assert isinstance(lineage.c.source_id.type, BIGINT)


def test_v013_constraints_indexes_and_weak_links_are_explicit() -> None:
    expected_uniques = {
        "analysis_explanations": "uq_analysis_explanations_identity",
        "analysis_lineage_records": "uq_analysis_lineage_records_identity",
        "metric_dependencies": "uq_metric_dependencies_identity",
    }
    for model in MODELS:
        table = model.__table__
        assert len(table.primary_key.columns) == 1
        assert any(isinstance(item, CheckConstraint) for item in table.constraints)
        assert any(
            isinstance(item, UniqueConstraint)
            and item.name == expected_uniques[table.name]
            for item in table.constraints
        )
        assert any(isinstance(item, Index) for item in table.indexes)
        assert not any(
            isinstance(item, ForeignKeyConstraint) for item in table.constraints
        )
        assert len(table.foreign_keys) == 0


def test_explanation_unique_identity_includes_module_and_versions() -> None:
    table = models.AnalysisExplanation.__table__
    unique = next(
        item for item in table.constraints
        if isinstance(item, UniqueConstraint)
        and item.name == "uq_analysis_explanations_identity"
    )
    assert tuple(column.name for column in unique.columns) == (
        "module_type", "entity_type", "entity_id", "analysis_as_of",
        "algorithm_version", "rule_set_version",
    )


def test_v013_mysql_ddl_compiles_without_cross_module_foreign_keys() -> None:
    for model in MODELS:
        ddl = str(CreateTable(model.__table__).compile(dialect=mysql.dialect()))
        assert f"CREATE TABLE {model.__tablename__}" in ddl
        assert "FOREIGN KEY" not in ddl
