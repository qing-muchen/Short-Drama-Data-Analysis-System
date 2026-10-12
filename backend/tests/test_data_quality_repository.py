"""Statement and transaction-boundary tests for data-quality repositories."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import create_autospec

import pytest
from sqlalchemy import ForeignKeyConstraint, UniqueConstraint, inspect
from sqlalchemy.dialects.mysql import dialect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.dml import Delete

from models.data_quality import (
    DataQualityRule,
    DataQualityRuleResult,
    DataQualityScore,
)
from repositories.data_quality_repository import (
    DataQualityRuleRepository,
    DataQualityRuleResultRepository,
    DataQualityScoreRepository,
)

SCORE_DATE = date(2026, 9, 16)
ANALYSIS_AS_OF = datetime(2026, 9, 16, 12, 0)
ALGORITHM_VERSION = "Quality Score V1.0"
RULE_SET_VERSION = "DQ Rules 1.0"
RULE_SET_HASH = "a" * 64


def make_session() -> Session:
    return create_autospec(Session, instance=True)


def rule_result_values(rule_id: int = 1) -> dict[str, object]:
    return {
        "quality_rule_id": rule_id,
        "result_status": "APPLIED",
        "applicable_count": 10,
        "passed_count": 8,
        "failed_count": 2,
        "rule_score": Decimal("80.00"),
        "evidence_summary": "8 of 10 records passed",
    }


def score_values(total_score: str = "80.00", grade: str = "A") -> dict[str, object]:
    return {
        "analysis_as_of": ANALYSIS_AS_OF,
        "completeness_score": Decimal("90.00"),
        "accuracy_score": Decimal("80.00"),
        "consistency_score": Decimal("70.00"),
        "timeliness_score": Decimal("60.00"),
        "total_score": Decimal(total_score),
        "quality_grade": grade,
        "algorithm_version": ALGORITHM_VERSION,
        "rule_set_hash": RULE_SET_HASH,
        "evaluated_entity_count": 100,
        "open_issue_count": 2,
    }


def test_rule_repository_queries_effective_rules_in_stable_order() -> None:
    session = make_session()
    expected = [DataQualityRule(rule_code="DQ_A", rule_version="1.0")]
    session.scalars.return_value.all.return_value = expected

    result = DataQualityRuleRepository(session).list_effective_rules(
        as_of=ANALYSIS_AS_OF,
        status="ACTIVE",
    )

    assert result == expected
    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "data_quality_rules.status = %s" in compiled
    assert "data_quality_rules.valid_from <= %s" in compiled
    assert "data_quality_rules.valid_to IS NULL" in compiled
    assert "data_quality_rules.valid_to > %s" in compiled
    assert "data_quality_rules.rule_code ASC" in compiled
    assert "data_quality_rules.rule_version ASC" in compiled
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_rule_repository_supports_dimension_and_rule_version_filters() -> None:
    session = make_session()
    session.scalars.return_value.all.return_value = []

    DataQualityRuleRepository(session).list_effective_rules(
        as_of=ANALYSIS_AS_OF,
        status="INACTIVE",
        dimension="ACCURACY",
        rule_version="2.0",
    )

    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "data_quality_rules.dimension = %s" in compiled
    assert "data_quality_rules.rule_version = %s" in compiled
    assert statement.compile(dialect=dialect()).params == {
        "status_1": "INACTIVE",
        "valid_from_1": ANALYSIS_AS_OF,
        "valid_to_1": ANALYSIS_AS_OF,
        "dimension_1": "ACCURACY",
        "rule_version_1": "2.0",
    }


def test_rule_repository_resolves_historical_rule_set_membership() -> None:
    session = make_session()
    session.scalars.return_value.all.return_value = []

    DataQualityRuleRepository(session).list_by_rule_set_version(
        rule_set_version=RULE_SET_VERSION,
        status="ACTIVE",
        dimension="COMPLETENESS",
    )

    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "INNER JOIN data_quality_rule_results" in compiled
    assert "INNER JOIN data_quality_scores" in compiled
    assert "data_quality_scores.rule_set_version = %s" in compiled
    assert "data_quality_rules.status = %s" in compiled
    assert "data_quality_rules.dimension = %s" in compiled
    assert "SELECT DISTINCT" in compiled
    assert "data_quality_rules.rule_code ASC" in compiled


def test_rule_repository_lists_future_rule_versions() -> None:
    session = make_session()
    session.scalars.return_value.all.return_value = []

    DataQualityRuleRepository(session).list_rule_versions(
        rule_code="DQ_REQUIRED_FIELDS",
        status="ACTIVE",
    )

    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "data_quality_rules.rule_code = %s" in compiled
    assert "data_quality_rules.status = %s" in compiled
    assert "data_quality_rules.valid_from DESC" in compiled
    assert "data_quality_rules.rule_version DESC" in compiled


def test_rule_result_repository_bulk_inserts_and_flushes_without_commit() -> None:
    session = make_session()
    repository = DataQualityRuleResultRepository(session)

    result = repository.bulk_create(
        quality_score_id=9,
        results=[rule_result_values(1), rule_result_values(2)],
    )

    assert [item.quality_rule_id for item in result] == [1, 2]
    assert all(item.quality_score_id == 9 for item in result)
    session.add_all.assert_called_once_with(result)
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_rule_result_repository_empty_bulk_still_flushes() -> None:
    session = make_session()

    result = DataQualityRuleResultRepository(session).bulk_create(
        quality_score_id=9,
        results=[],
    )

    assert result == []
    session.add_all.assert_called_once_with([])
    session.flush.assert_called_once_with()


def test_rule_result_repository_uses_v009_fields_only() -> None:
    session = make_session()

    with pytest.raises(ValueError, match="actual_value"):
        DataQualityRuleResultRepository(session).bulk_create(
            quality_score_id=9,
            results=[
                {
                    **rule_result_values(),
                    "actual_value": "unexpected non-V009 field",
                }
            ],
        )

    session.add_all.assert_not_called()
    session.flush.assert_not_called()


def test_rule_result_query_eager_loads_rules_in_one_stable_query() -> None:
    session = make_session()
    expected = [DataQualityRuleResult(**rule_result_values())]
    session.scalars.return_value.unique.return_value.all.return_value = expected

    result = DataQualityRuleResultRepository(session).list_by_score_id(
        quality_score_id=9
    )

    assert result == expected
    session.scalars.assert_called_once()
    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "INNER JOIN data_quality_rules" in compiled
    assert "data_quality_rule_results.quality_score_id = %s" in compiled
    assert "data_quality_rules.rule_code ASC" in compiled
    assert "data_quality_rules.rule_version ASC" in compiled


def test_score_repository_saves_and_flushes_without_commit() -> None:
    session = make_session()
    values = {
        **score_values(),
        "score_date": SCORE_DATE,
        "rule_set_version": RULE_SET_VERSION,
        "score_scope_type": "ALL",
        "score_scope_id": 0,
    }

    result = DataQualityScoreRepository(session).save_score(values)

    assert result.score_date == SCORE_DATE
    assert result.rule_set_version == RULE_SET_VERSION
    session.add.assert_called_once_with(result)
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_score_repository_replaces_exact_scope_collection() -> None:
    session = make_session()
    repository = DataQualityScoreRepository(session)

    result = repository.replace_scope_scores(
        score_date=SCORE_DATE,
        rule_set_version=RULE_SET_VERSION,
        score_scope_type="ALL",
        score_scope_id=0,
        scores=[score_values()],
    )

    assert len(result) == 1
    assert result[0].score_date == SCORE_DATE
    assert result[0].rule_set_version == RULE_SET_VERSION
    assert result[0].score_scope_type == "ALL"
    assert result[0].score_scope_id == 0
    delete_statement = session.execute.call_args.args[0]
    assert isinstance(delete_statement, Delete)
    compiled = str(delete_statement.compile(dialect=dialect()))
    assert "DELETE FROM data_quality_scores" in compiled
    assert "data_quality_scores.score_date = %s" in compiled
    assert "data_quality_scores.rule_set_version = %s" in compiled
    assert "data_quality_scores.score_scope_type = %s" in compiled
    assert "data_quality_scores.score_scope_id = %s" in compiled
    session.add_all.assert_called_once_with(result)
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()


def test_score_repository_empty_replacement_cleans_scope() -> None:
    session = make_session()

    result = DataQualityScoreRepository(session).replace_scope_scores(
        score_date=SCORE_DATE,
        rule_set_version=RULE_SET_VERSION,
        score_scope_type="ALL",
        score_scope_id=0,
        scores=[],
    )

    assert result == []
    assert isinstance(session.execute.call_args.args[0], Delete)
    session.add_all.assert_called_once_with([])
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()


def test_score_repository_returns_latest_date_and_none() -> None:
    session = make_session()
    repository = DataQualityScoreRepository(session)
    session.scalar.return_value = SCORE_DATE

    assert repository.get_latest_score_date(
        score_scope_type="ALL",
        score_scope_id=0,
        algorithm_version=ALGORITHM_VERSION,
        rule_set_version=RULE_SET_VERSION,
    ) == SCORE_DATE
    statement = session.scalar.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "max(data_quality_scores.score_date)" in compiled
    assert "data_quality_scores.algorithm_version = %s" in compiled
    assert "data_quality_scores.rule_set_version = %s" in compiled

    session.scalar.return_value = None
    assert repository.get_latest_score_date(
        score_scope_type="ALL",
        score_scope_id=0,
    ) is None


def test_current_score_eager_loads_full_rule_graph_without_n_plus_one() -> None:
    session = make_session()
    expected = DataQualityScore(
        **score_values(),
        score_date=SCORE_DATE,
        rule_set_version=RULE_SET_VERSION,
        score_scope_type="ALL",
        score_scope_id=0,
    )
    session.execute.return_value.unique.return_value.scalar_one_or_none.return_value = (
        expected
    )

    result = DataQualityScoreRepository(session).get_current_score(
        score_scope_type="ALL",
        score_scope_id=0,
        algorithm_version=ALGORITHM_VERSION,
        rule_set_version=RULE_SET_VERSION,
    )

    assert result is expected
    session.execute.assert_called_once()
    statement = session.execute.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "LEFT OUTER JOIN data_quality_rule_results" in compiled
    assert "LEFT OUTER JOIN data_quality_rules" in compiled
    assert "data_quality_scores.score_date DESC" in compiled
    assert "data_quality_scores.analysis_as_of DESC" in compiled
    assert statement._limit_clause.value == 1


def test_history_query_returns_latest_window_in_chronological_order() -> None:
    session = make_session()
    session.scalars.return_value.all.return_value = []

    result = DataQualityScoreRepository(session).list_history(
        score_scope_type="ALL",
        score_scope_id=0,
        algorithm_version=ALGORITHM_VERSION,
        rule_set_version=RULE_SET_VERSION,
        start_date=date(2026, 9, 1),
        end_date=SCORE_DATE,
        limit=30,
    )

    assert result == []
    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "data_quality_scores.score_date >= %s" in compiled
    assert "data_quality_scores.score_date <= %s" in compiled
    assert "data_quality_scores.score_date DESC" in compiled
    assert "LIMIT %s" in compiled
    assert "FROM (SELECT" in compiled
    assert "AS recent_quality_score_ids" in compiled
    assert "data_quality_scores.score_date ASC" in compiled
    assert statement._order_by_clauses[0].modifier.__name__ == "asc_op"


def test_grade_distribution_fills_missing_grades_and_handles_no_data() -> None:
    session = make_session()
    repository = DataQualityScoreRepository(session)
    session.execute.return_value.all.return_value = [("S", 2), ("B", 3)]

    distribution = repository.get_grade_distribution(
        score_date=SCORE_DATE,
        score_scope_type="ALL",
        score_scope_id=0,
        algorithm_version=ALGORITHM_VERSION,
        rule_set_version=RULE_SET_VERSION,
    )

    assert distribution == {"S": 2, "A": 0, "B": 3, "C": 0}
    statement = session.execute.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "count(data_quality_scores.quality_score_id)" in compiled
    assert "GROUP BY data_quality_scores.quality_grade" in compiled

    session.execute.return_value.all.return_value = []
    assert repository.get_grade_distribution(
        score_date=SCORE_DATE,
        score_scope_type="ALL",
        score_scope_id=0,
    ) == {"S": 0, "A": 0, "B": 0, "C": 0}


def test_unique_and_foreign_key_constraints_match_repository_identity() -> None:
    score_unique = next(
        constraint
        for constraint in inspect(DataQualityScore).local_table.constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_data_quality_scores_identity"
    )
    result_unique = next(
        constraint
        for constraint in inspect(DataQualityRuleResult).local_table.constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_data_quality_rule_results_score_rule"
    )
    result_foreign_keys = {
        constraint.name: next(iter(constraint.elements))
        for constraint in inspect(DataQualityRuleResult).local_table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    }

    assert tuple(score_unique.columns.keys()) == (
        "score_date",
        "algorithm_version",
        "rule_set_version",
        "rule_set_hash",
        "score_scope_type",
        "score_scope_id",
    )
    assert tuple(result_unique.columns.keys()) == (
        "quality_score_id",
        "quality_rule_id",
    )
    assert result_foreign_keys[
        "fk_data_quality_rule_results_score"
    ].target_fullname == "data_quality_scores.quality_score_id"
    assert result_foreign_keys[
        "fk_data_quality_rule_results_rule"
    ].target_fullname == "data_quality_rules.quality_rule_id"


@pytest.mark.parametrize("repository_kind", ["score", "result"])
def test_database_integrity_errors_propagate_for_service_rollback(
    repository_kind: str,
) -> None:
    session = make_session()
    session.flush.side_effect = IntegrityError(
        "INSERT",
        {},
        RuntimeError("unique or foreign-key constraint"),
    )

    with pytest.raises(IntegrityError):
        if repository_kind == "score":
            DataQualityScoreRepository(session).save_score(
                {
                    **score_values(),
                    "score_date": SCORE_DATE,
                    "rule_set_version": RULE_SET_VERSION,
                    "score_scope_type": "ALL",
                    "score_scope_id": 0,
                }
            )
        else:
            DataQualityRuleResultRepository(session).bulk_create(
                quality_score_id=999,
                results=[rule_result_values(999)],
            )

    session.commit.assert_not_called()
    session.rollback.assert_not_called()
