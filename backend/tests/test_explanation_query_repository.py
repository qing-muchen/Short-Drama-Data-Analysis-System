"""Tests for read-only Phase 6.2 explanation query repositories."""

from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.dialects.mysql import dialect
from sqlalchemy.orm import Session

from models.explanation import AnalysisExplanation, AnalysisLineageRecord
from repositories.explanation_query_repository import (
    AnalysisExplanationQueryRepository,
    AnalysisLineageQueryRepository,
)


AS_OF = datetime(2026, 9, 22, tzinfo=timezone.utc)


def make_session() -> Session:
    return create_autospec(Session, instance=True)


def test_entity_query_supports_filters_and_pagination() -> None:
    session = make_session()
    session.scalar.return_value = 2
    session.scalars.return_value.all.return_value = [
        AnalysisExplanation(explanation_id=1, entity_type="SCORE", entity_id=10)
    ]

    page = AnalysisExplanationQueryRepository(session).get_explanations_by_entity(
        entity_type="SCORE",
        entity_id=10,
        module_type="SCORE",
        analysis_as_of=AS_OF,
        algorithm_version="Composite Score V1.0",
        rule_set_version="N/A",
        page=2,
        page_size=1,
    )

    assert page.page == 2
    assert page.page_size == 1
    assert page.total == 2
    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "analysis_explanations.entity_type = %s" in compiled
    assert "analysis_explanations.entity_id = %s" in compiled
    assert "analysis_explanations.module_type = %s" in compiled
    assert "analysis_explanations.analysis_as_of <= %s" in compiled
    assert "analysis_explanations.algorithm_version = %s" in compiled
    assert "analysis_explanations.rule_set_version = %s" in compiled
    assert "analysis_explanations.analysis_as_of DESC" in compiled
    assert statement._offset_clause.value == 1
    assert statement._limit_clause.value == 1


def test_latest_query_uses_stable_descending_order() -> None:
    session = make_session()
    expected = AnalysisExplanation(explanation_id=9)
    session.scalar.return_value = expected

    result = AnalysisExplanationQueryRepository(session).get_latest_explanation(
        entity_type="SCORE",
        entity_id=10,
        module_type="SCORE",
    )

    assert result is expected
    statement = session.scalar.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "analysis_explanations.analysis_as_of DESC" in compiled
    assert "analysis_explanations.explanation_id DESC" in compiled
    assert statement._limit_clause.value == 1


def test_lineage_query_supports_source_and_relationship_filters() -> None:
    session = make_session()
    expected = [AnalysisLineageRecord(lineage_id=1)]
    session.scalars.return_value.all.return_value = expected

    result = AnalysisLineageQueryRepository(session).get_lineage_by_target(
        target_type="EXPLANATION",
        target_id=5,
        source_type="SNAPSHOT",
        relationship_type="USES_WINDOW",
    )

    assert result == expected
    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "analysis_lineage_records.target_type = %s" in compiled
    assert "analysis_lineage_records.target_id = %s" in compiled
    assert "analysis_lineage_records.source_type = %s" in compiled
    assert "analysis_lineage_records.relationship_type = %s" in compiled
    assert "analysis_lineage_records.created_at ASC" in compiled
    assert "analysis_lineage_records.lineage_id ASC" in compiled


def test_query_repositories_do_not_manage_transactions_or_create_sessions() -> None:
    session = make_session()
    explanation_repository = AnalysisExplanationQueryRepository(session)
    lineage_repository = AnalysisLineageQueryRepository(session)

    assert explanation_repository.session is session
    assert lineage_repository.session is session
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
    session.close.assert_not_called()
