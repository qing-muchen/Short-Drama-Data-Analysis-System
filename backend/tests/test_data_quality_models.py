"""ORM contract tests for the Phase 2 data-quality schema."""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, inspect
from sqlalchemy.dialects.mysql import BIGINT, JSON
from sqlalchemy.orm import configure_mappers

import models
from database.base import Base


def _named_constraints(table_name: str, kind: type[object]) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, kind) and constraint.name is not None
    }


def test_data_quality_models_register_without_business_scope_relationships() -> None:
    configure_mappers()

    assert {
        "data_quality_rules",
        "data_quality_rule_results",
        "data_quality_scores",
    }.issubset(Base.metadata.tables)
    assert {"results"}.issubset(
        inspect(models.DataQualityRule).relationships.keys()
    )
    assert {"rule", "score"}.issubset(
        inspect(models.DataQualityRuleResult).relationships.keys()
    )
    assert {"rule_results"}.issubset(
        inspect(models.DataQualityScore).relationships.keys()
    )
    assert "quality_scores" not in inspect(models.Drama).relationships


def test_data_quality_score_is_global_all_scope() -> None:
    table = Base.metadata.tables["data_quality_scores"]

    assert {"score_scope_type", "score_scope_id"}.issubset(table.c.keys())
    assert {"drama_id", "platform_id", "tag_id"}.isdisjoint(table.c.keys())
    assert isinstance(table.c.quality_score_id.type, BIGINT)
    assert table.c.quality_score_id.type.unsigned
    assert isinstance(table.c.source_watermark.type, JSON)
    assert _named_constraints("data_quality_scores", CheckConstraint) == {
        "chk_data_quality_scores_algorithm",
        "chk_data_quality_scores_counts",
        "chk_data_quality_scores_dimensions",
        "chk_data_quality_scores_grade",
        "chk_data_quality_scores_hash",
        "chk_data_quality_scores_rule_set",
        "chk_data_quality_scores_scope",
        "chk_data_quality_scores_total",
    }


def test_rule_result_relations_and_constraints_match_v009() -> None:
    table = Base.metadata.tables["data_quality_rule_results"]

    assert _named_constraints("data_quality_rule_results", UniqueConstraint) == {
        "uq_data_quality_rule_results_score_rule"
    }
    assert _named_constraints("data_quality_rule_results", CheckConstraint) == {
        "chk_data_quality_rule_results_counts",
        "chk_data_quality_rule_results_score",
        "chk_data_quality_rule_results_state",
        "chk_data_quality_rule_results_status",
    }
    foreign_keys = {
        constraint.name: next(iter(constraint.elements))
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }
    assert foreign_keys["fk_data_quality_rule_results_score"].ondelete == "CASCADE"
    assert foreign_keys["fk_data_quality_rule_results_score"].onupdate == "RESTRICT"
    assert foreign_keys["fk_data_quality_rule_results_rule"].ondelete == "RESTRICT"
    assert foreign_keys["fk_data_quality_rule_results_rule"].onupdate == "RESTRICT"


def test_data_quality_rule_configuration_and_version_identity() -> None:
    table = Base.metadata.tables["data_quality_rules"]

    assert isinstance(table.c.configuration.type, JSON)
    assert _named_constraints("data_quality_rules", UniqueConstraint) == {
        "uq_data_quality_rules_code_version"
    }
    assert len(_named_constraints("data_quality_rules", CheckConstraint)) == 11
