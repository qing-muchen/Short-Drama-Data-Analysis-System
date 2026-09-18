"""Import-only verification for the current 23-table ORM mapping."""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, inspect
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.orm import configure_mappers

import models
from database.base import Base


EXPECTED_TABLES = {
    "users",
    "dramas",
    "actors",
    "directors",
    "companies",
    "platforms",
    "tags",
    "drama_actors",
    "drama_directors",
    "drama_companies",
    "drama_tags",
    "drama_platforms",
    "drama_metric_snapshots",
    "drama_metric_snapshot_revisions",
    "drama_scores",
    "import_jobs",
    "import_errors",
    "data_quality_issues",
    "data_quality_rules",
    "data_quality_rule_results",
    "data_quality_scores",
    "operation_logs",
    "prediction_results",
}


def test_all_models_import_and_configure() -> None:
    """All model classes load and every relationship resolves without a DB."""

    assert len(models.__all__) == 23
    configure_mappers()
    assert {
        "actor_relations",
        "director_relations",
        "company_relations",
        "tag_relations",
        "platform_relations",
    }.issubset(inspect(models.Drama).relationships.keys())
    assert "snapshots" in inspect(models.DramaPlatform).relationships
    assert {
        "revisions",
        "current_revision",
        "source_import_job",
    }.issubset(inspect(models.DramaMetricSnapshot).relationships.keys())
    assert "scores" in inspect(models.Drama).relationships
    assert "drama" in inspect(models.DramaScore).relationships
    assert "errors" in inspect(models.ImportJob).relationships
    assert "results" in inspect(models.DataQualityRule).relationships
    assert {"rule", "score"}.issubset(
        inspect(models.DataQualityRuleResult).relationships.keys()
    )
    assert "rule_results" in inspect(models.DataQualityScore).relationships
    assert "predictions" in inspect(models.Drama).relationships
    assert "drama" in inspect(models.PredictionResult).relationships


def test_metadata_matches_frozen_schema_shape() -> None:
    """Metadata preserves table, PK, FK, CHECK, and UNIQUE baseline counts."""

    assert set(Base.metadata.tables) == EXPECTED_TABLES

    tables = tuple(Base.metadata.tables.values())
    assert all(len(table.primary_key.columns) == 1 for table in tables)
    assert all(
        isinstance(next(iter(table.primary_key.columns)).type, BIGINT)
        and next(iter(table.primary_key.columns)).type.unsigned
        and next(iter(table.primary_key.columns)).autoincrement is True
        for table in tables
    )

    foreign_keys = sum(
        isinstance(constraint, ForeignKeyConstraint)
        for table in tables
        for constraint in table.constraints
    )
    checks = sum(
        isinstance(constraint, CheckConstraint)
        for table in tables
        for constraint in table.constraints
    )
    uniques = sum(
        isinstance(constraint, UniqueConstraint)
        and constraint.name is not None
        for table in tables
        for constraint in table.constraints
    )

    assert foreign_keys == 43
    assert all(
        constraint.name is not None
        for table in tables
        for constraint in table.foreign_key_constraints
    )
    assert checks == 89
    assert uniques == 21
    assert sum(len(table.indexes) for table in tables) == 59
    assert all(
        foreign_key.ondelete in {"RESTRICT", "CASCADE"}
        and foreign_key.onupdate == "RESTRICT"
        for table in tables
        for foreign_key in table.foreign_keys
    )

    cascade_foreign_keys = [
        foreign_key
        for table in tables
        for foreign_key in table.foreign_keys
        if foreign_key.ondelete == "CASCADE"
    ]
    assert len(cascade_foreign_keys) == 1
    assert cascade_foreign_keys[0].parent.table.name == "data_quality_rule_results"
    assert cascade_foreign_keys[0].column.table.name == "data_quality_scores"


def test_snapshot_and_governance_models_remain_separate() -> None:
    """Special schema designs remain explicit rather than JSON/polymorphic fields."""

    snapshot = Base.metadata.tables["drama_metric_snapshots"]
    revision = Base.metadata.tables["drama_metric_snapshot_revisions"]
    quality = Base.metadata.tables["data_quality_issues"]
    operation = Base.metadata.tables["operation_logs"]
    score = Base.metadata.tables["drama_scores"]

    assert "current_revision_id" in snapshot.c
    assert "revision_action" in revision.c
    assert {
        "target_snapshot_revision_id",
        "target_drama_platform_id",
        "target_drama_id",
    }.issubset(quality.c.keys())
    assert "target_type" not in quality.c
    assert "target_id" not in quality.c
    assert "target_json" not in operation.c
    assert {
        "score_scope_type",
        "score_scope_id",
        "analysis_as_of",
        "algorithm_version",
    }.issubset(score.c.keys())
    assert "calculated_by_user_id" not in score.c
    assert set(score.c.keys()).isdisjoint(
        {"drama_name", "play_count", "like_count", "comment_count"}
    )
