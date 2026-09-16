"""Versioned data-quality rule, execution-result, and score ORM mappings."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    desc,
    text,
)
from sqlalchemy.dialects.mysql import BIGINT, CHAR, DATETIME, DECIMAL, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base
from models.common import CreatedUpdatedAtMixin


class DataQualityRule(CreatedUpdatedAtMixin, Base):
    """One immutable, versioned data-quality rule definition."""

    __tablename__ = "data_quality_rules"
    __table_args__ = (
        UniqueConstraint(
            "rule_code",
            "rule_version",
            name="uq_data_quality_rules_code_version",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(rule_code)) > 0",
            name="chk_data_quality_rules_code",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(rule_version)) > 0",
            name="chk_data_quality_rules_version",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(rule_name)) > 0",
            name="chk_data_quality_rules_name",
        ),
        CheckConstraint(
            "dimension IN ('COMPLETENESS', 'ACCURACY', 'CONSISTENCY', 'TIMELINESS')",
            name="chk_data_quality_rules_dimension",
        ),
        CheckConstraint(
            "target_entity_type IN ('DRAMA', 'DRAMA_PLATFORM', 'SNAPSHOT', 'IMPORT_JOB')",
            name="chk_data_quality_rules_target",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(evaluator_key)) > 0",
            name="chk_data_quality_rules_evaluator",
        ),
        CheckConstraint(
            "scoring_method IN ('PASS_RATE', 'BUCKET_AVERAGE')",
            name="chk_data_quality_rules_scoring",
        ),
        CheckConstraint(
            "weight > 0 AND weight <= 1",
            name="chk_data_quality_rules_weight",
        ),
        CheckConstraint(
            "severity IN ('INFO', 'WARNING', 'ERROR')",
            name="chk_data_quality_rules_severity",
        ),
        CheckConstraint(
            "status IN ('DRAFT', 'ACTIVE', 'INACTIVE')",
            name="chk_data_quality_rules_status",
        ),
        CheckConstraint(
            "valid_to IS NULL OR valid_to > valid_from",
            name="chk_data_quality_rules_validity",
        ),
        Index(
            "idx_data_quality_rules_active",
            "status",
            "dimension",
            "valid_from",
            "valid_to",
        ),
        Index(
            "idx_data_quality_rules_target",
            "target_entity_type",
            "dimension",
            "status",
        ),
        Index("idx_data_quality_rules_code_status", "rule_code", "status"),
    )

    quality_rule_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    rule_code: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_name: Mapped[str] = mapped_column(String(200), nullable=False)
    dimension: Mapped[str] = mapped_column(String(32), nullable=False)
    target_entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    evaluator_key: Mapped[str] = mapped_column(String(64), nullable=False)
    scoring_method: Mapped[str] = mapped_column(String(32), nullable=False)
    weight: Mapped[Decimal] = mapped_column(DECIMAL(7, 6), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'DRAFT'")
    )
    valid_from: Mapped[datetime] = mapped_column(DATETIME(fsp=6), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    results: Mapped[list["DataQualityRuleResult"]] = relationship(
        back_populates="rule"
    )


class DataQualityScore(CreatedUpdatedAtMixin, Base):
    """One global quality score for a date, algorithm, rule set, and scope."""

    __tablename__ = "data_quality_scores"
    __table_args__ = (
        UniqueConstraint(
            "score_date",
            "algorithm_version",
            "rule_set_version",
            "rule_set_hash",
            "score_scope_type",
            "score_scope_id",
            name="uq_data_quality_scores_identity",
        ),
        CheckConstraint(
            "score_scope_type = 'ALL' AND score_scope_id = 0",
            name="chk_data_quality_scores_scope",
        ),
        CheckConstraint(
            "completeness_score BETWEEN 0 AND 100 "
            "AND accuracy_score BETWEEN 0 AND 100 "
            "AND consistency_score BETWEEN 0 AND 100 "
            "AND timeliness_score BETWEEN 0 AND 100",
            name="chk_data_quality_scores_dimensions",
        ),
        CheckConstraint(
            "total_score BETWEEN 0 AND 100",
            name="chk_data_quality_scores_total",
        ),
        CheckConstraint(
            "quality_grade IN ('S', 'A', 'B', 'C')",
            name="chk_data_quality_scores_grade",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(algorithm_version)) > 0",
            name="chk_data_quality_scores_algorithm",
        ),
        CheckConstraint(
            "CHAR_LENGTH(TRIM(rule_set_version)) > 0",
            name="chk_data_quality_scores_rule_set",
        ),
        CheckConstraint(
            "CHAR_LENGTH(rule_set_hash) = 64",
            name="chk_data_quality_scores_hash",
        ),
        CheckConstraint(
            "evaluated_entity_count >= 0 AND open_issue_count >= 0",
            name="chk_data_quality_scores_counts",
        ),
        Index(
            "idx_data_quality_scores_scope_date",
            "score_scope_type",
            "score_scope_id",
            desc("score_date"),
        ),
        Index(
            "idx_data_quality_scores_version_date",
            "algorithm_version",
            "rule_set_version",
            desc("score_date"),
        ),
        Index(
            "idx_data_quality_scores_grade_date",
            "quality_grade",
            desc("score_date"),
        ),
    )

    quality_score_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    score_date: Mapped[date] = mapped_column(nullable=False)
    score_scope_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'ALL'")
    )
    score_scope_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, server_default=text("0")
    )
    analysis_as_of: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6), nullable=False
    )
    completeness_score: Mapped[Decimal] = mapped_column(
        DECIMAL(5, 2), nullable=False
    )
    accuracy_score: Mapped[Decimal] = mapped_column(DECIMAL(5, 2), nullable=False)
    consistency_score: Mapped[Decimal] = mapped_column(
        DECIMAL(5, 2), nullable=False
    )
    timeliness_score: Mapped[Decimal] = mapped_column(
        DECIMAL(5, 2), nullable=False
    )
    total_score: Mapped[Decimal] = mapped_column(DECIMAL(5, 2), nullable=False)
    quality_grade: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_set_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_set_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False)
    evaluated_entity_count: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, server_default=text("0")
    )
    open_issue_count: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, server_default=text("0")
    )
    source_watermark: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )

    rule_results: Mapped[list["DataQualityRuleResult"]] = relationship(
        back_populates="score",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DataQualityRuleResult(Base):
    """One rule-version execution fact belonging to a quality score."""

    __tablename__ = "data_quality_rule_results"
    __table_args__ = (
        UniqueConstraint(
            "quality_score_id",
            "quality_rule_id",
            name="uq_data_quality_rule_results_score_rule",
        ),
        CheckConstraint(
            "result_status IN ('APPLIED', 'NOT_APPLICABLE')",
            name="chk_data_quality_rule_results_status",
        ),
        CheckConstraint(
            "applicable_count = passed_count + failed_count",
            name="chk_data_quality_rule_results_counts",
        ),
        CheckConstraint(
            "rule_score IS NULL OR rule_score BETWEEN 0 AND 100",
            name="chk_data_quality_rule_results_score",
        ),
        CheckConstraint(
            "(result_status = 'APPLIED' AND applicable_count > 0 "
            "AND rule_score IS NOT NULL AND not_applicable_reason IS NULL) "
            "OR (result_status = 'NOT_APPLICABLE' AND applicable_count = 0 "
            "AND passed_count = 0 AND failed_count = 0 AND rule_score IS NULL "
            "AND not_applicable_reason IS NOT NULL "
            "AND CHAR_LENGTH(TRIM(not_applicable_reason)) > 0)",
            name="chk_data_quality_rule_results_state",
        ),
        Index(
            "idx_data_quality_rule_results_score_status",
            "quality_score_id",
            "result_status",
        ),
        Index(
            "idx_data_quality_rule_results_rule_score",
            "quality_rule_id",
            "quality_score_id",
        ),
        Index(
            "idx_data_quality_rule_results_failures",
            "quality_score_id",
            desc("failed_count"),
        ),
    )

    quality_rule_result_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), primary_key=True, autoincrement=True
    )
    quality_score_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "data_quality_scores.quality_score_id",
            name="fk_data_quality_rule_results_score",
            ondelete="CASCADE",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    quality_rule_id: Mapped[int] = mapped_column(
        BIGINT(unsigned=True),
        ForeignKey(
            "data_quality_rules.quality_rule_id",
            name="fk_data_quality_rule_results_rule",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )
    result_status: Mapped[str] = mapped_column(String(24), nullable=False)
    applicable_count: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, server_default=text("0")
    )
    passed_count: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, server_default=text("0")
    )
    failed_count: Mapped[int] = mapped_column(
        BIGINT(unsigned=True), nullable=False, server_default=text("0")
    )
    rule_score: Mapped[Decimal | None] = mapped_column(
        DECIMAL(5, 2), nullable=True
    )
    not_applicable_reason: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    evidence_summary: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DATETIME(fsp=6),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP(6)"),
    )

    rule: Mapped[DataQualityRule] = relationship(back_populates="results")
    score: Mapped[DataQualityScore] = relationship(back_populates="rule_results")


__all__ = (
    "DataQualityRule",
    "DataQualityRuleResult",
    "DataQualityScore",
)
