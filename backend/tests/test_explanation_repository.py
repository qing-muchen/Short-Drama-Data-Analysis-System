"""Repository boundary tests for V013 explanation persistence."""

from datetime import datetime, timezone
from unittest.mock import create_autospec

from sqlalchemy.dialects.mysql import dialect
from sqlalchemy.orm import Session

from models.explanation import AnalysisExplanation, AnalysisLineageRecord
from repositories.explanation_repository import (
    AnalysisExplanationRepository,
    AnalysisLineageRepository,
)


AS_OF = datetime(2026, 9, 22, tzinfo=timezone.utc)


def make_session() -> Session:
    return create_autospec(Session, instance=True)


def make_explanation(
    *,
    analysis_as_of: datetime = AS_OF,
    algorithm_version: str = "Composite Score V1.0",
) -> AnalysisExplanation:
    return AnalysisExplanation(
        entity_type="SCORE",
        entity_id=10,
        module_type="SCORE",
        summary="Growth is relatively weak.",
        detail={"reason": "Growth is relatively weak."},
        algorithm_version=algorithm_version,
        rule_set_version="N/A",
        analysis_as_of=analysis_as_of,
    )


def make_lineage(*, target_id: int = 1) -> AnalysisLineageRecord:
    return AnalysisLineageRecord(
        target_type="EXPLANATION",
        target_id=target_id,
        source_type="METRIC",
        source_id=10,
        relationship_type="DERIVED_FROM",
        analysis_as_of=AS_OF,
    )


def test_create_explanation_adds_and_flushes_without_commit() -> None:
    session = make_session()
    explanation = make_explanation()

    result = AnalysisExplanationRepository(session).create_explanation(explanation)

    assert result is explanation
    session.add.assert_called_once_with(explanation)
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_get_by_identity_matches_all_identity_columns() -> None:
    session = make_session()
    expected = make_explanation()
    session.scalar.return_value = expected

    result = AnalysisExplanationRepository(session).get_by_identity(
        module_type="SCORE",
        entity_type="SCORE",
        entity_id=10,
        analysis_as_of=AS_OF,
        algorithm_version="Composite Score V1.0",
        rule_set_version="N/A",
    )

    assert result is expected
    statement = session.scalar.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    for column in (
        "module_type",
        "entity_type",
        "entity_id",
        "analysis_as_of",
        "algorithm_version",
        "rule_set_version",
    ):
        assert f"analysis_explanations.{column} = %s" in compiled


def test_different_versions_and_analysis_dates_are_queryable_as_distinct_rows() -> None:
    session = make_session()
    first = make_explanation()
    second = make_explanation(algorithm_version="Composite Score V2.0")
    third = make_explanation(
        analysis_as_of=datetime(2026, 9, 23, tzinfo=timezone.utc)
    )
    session.scalars.return_value.all.return_value = [first, second, third]

    rows = AnalysisExplanationRepository(session).get_by_entity(
        entity_type="SCORE",
        entity_id=10,
    )

    assert rows == [first, second, third]
    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "analysis_explanations.analysis_as_of DESC" in compiled
    assert "analysis_explanations.explanation_id DESC" in compiled


def test_create_many_lineage_flushes_batch_without_commit() -> None:
    session = make_session()
    records = [make_lineage(target_id=1), make_lineage(target_id=2)]

    result = AnalysisLineageRepository(session).create_many(records)

    assert result == records
    session.add_all.assert_called_once_with(records)
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_get_by_target_filters_target_and_orders_creation() -> None:
    session = make_session()
    records = [make_lineage(target_id=1)]
    session.scalars.return_value.all.return_value = records

    result = AnalysisLineageRepository(session).get_by_target(
        target_type="EXPLANATION",
        target_id=1,
    )

    assert result == records
    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "analysis_lineage_records.target_type = %s" in compiled
    assert "analysis_lineage_records.target_id = %s" in compiled
    assert "analysis_lineage_records.created_at ASC" in compiled
    assert "analysis_lineage_records.lineage_id ASC" in compiled


def test_repository_does_not_create_sessions_or_manage_transactions() -> None:
    session = make_session()
    repository = AnalysisExplanationRepository(session)

    assert repository.session is session
    assert not hasattr(repository, "sessionmaker")
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
