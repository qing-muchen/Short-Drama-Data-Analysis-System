"""Statement and transaction-boundary tests for ScoreRepository."""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import create_autospec

from sqlalchemy import UniqueConstraint, inspect
from sqlalchemy.dialects.mysql import dialect
from sqlalchemy.orm import Session
from sqlalchemy.sql.dml import Delete

from models.drama import Drama
from models.score import DramaScore
from repositories.score_repository import ScoreRepository

SCORE_DATE = date(2026, 9, 14)
VERSION = "Composite Score V1.0"


def make_session() -> Session:
    return create_autospec(Session, instance=True)


def score_values(drama_id: int, total_score: str, level: str) -> dict[str, object]:
    return {
        "drama_id": drama_id,
        "analysis_as_of": datetime(2026, 9, 14, 12, 0),
        "heat_score": Decimal("80.00"),
        "growth_score": Decimal("70.00"),
        "engagement_score": Decimal("60.00"),
        "lifecycle_score": Decimal("40.00"),
        "total_score": Decimal(total_score),
        "level": level,
    }


def test_replace_scope_scores_inserts_complete_collection_without_commit() -> None:
    session = make_session()
    repository = ScoreRepository(session)

    result = repository.replace_scope_scores(
        score_date=SCORE_DATE,
        algorithm_version=VERSION,
        score_scope_type="ALL",
        score_scope_id=0,
        scores=[score_values(1, "80.00", "A"), score_values(2, "65.00", "B")],
    )

    assert [item.drama_id for item in result] == [1, 2]
    assert all(item.score_date == SCORE_DATE for item in result)
    assert all(item.algorithm_version == VERSION for item in result)
    assert all(item.score_scope_type == "ALL" for item in result)
    assert all(item.score_scope_id == 0 for item in result)
    session.add_all.assert_called_once_with(result)
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()


def test_replace_scope_scores_deletes_old_scope_even_when_replacement_is_empty() -> None:
    session = make_session()
    repository = ScoreRepository(session)

    result = repository.replace_scope_scores(
        score_date=SCORE_DATE,
        algorithm_version=VERSION,
        score_scope_type="ALL",
        score_scope_id=0,
        scores=[],
    )

    assert result == []
    delete_statement = session.execute.call_args.args[0]
    assert isinstance(delete_statement, Delete)
    compiled = str(delete_statement.compile(dialect=dialect()))
    assert "DELETE FROM drama_scores" in compiled
    assert "drama_scores.score_date = %s" in compiled
    assert "drama_scores.algorithm_version = %s" in compiled
    assert "drama_scores.score_scope_type = %s" in compiled
    assert "drama_scores.score_scope_id = %s" in compiled
    session.add_all.assert_called_once_with([])
    session.flush.assert_called_once_with()
    session.commit.assert_not_called()


def test_drama_score_unique_constraint_covers_full_scope_identity() -> None:
    identity = next(
        constraint
        for constraint in inspect(DramaScore).local_table.constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_drama_scores_identity"
    )

    assert tuple(identity.columns.keys()) == (
        "drama_id",
        "score_date",
        "algorithm_version",
        "score_scope_type",
        "score_scope_id",
    )


def test_paginate_ranking_builds_filters_and_stable_database_order() -> None:
    session = make_session()
    first = DramaScore(**score_values(1, "90.00", "S"))
    session.scalar.return_value = 3
    session.scalars.return_value.all.return_value = [first]

    page = ScoreRepository(session).paginate_ranking(
        score_date=SCORE_DATE,
        algorithm_version=VERSION,
        score_scope_type="ALL",
        score_scope_id=0,
        level="S",
        page=2,
        page_size=1,
    )

    assert page.page == 2
    assert page.page_size == 1
    assert page.total == 3
    assert page.items == [first]
    statement = session.scalars.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "INNER JOIN dramas" in compiled
    assert "drama_scores.level = %s" in compiled
    assert "drama_scores.total_score DESC" in compiled
    assert "drama_scores.heat_score DESC" in compiled
    assert "drama_scores.growth_score DESC" in compiled
    assert "dramas.drama_code ASC" in compiled
    assert statement._offset_clause.value == 1
    assert statement._limit_clause.value == 1
    session.commit.assert_not_called()


def test_get_latest_by_drama_uses_descending_stable_order() -> None:
    session = make_session()
    expected = DramaScore(**score_values(7, "88.00", "A"))
    session.scalar.return_value = expected

    result = ScoreRepository(session).get_latest_by_drama(
        drama_id=7,
        algorithm_version=VERSION,
        score_scope_type="ALL",
        score_scope_id=0,
    )

    assert result is expected
    statement = session.scalar.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "drama_scores.drama_id = %s" in compiled
    assert "drama_scores.score_date DESC" in compiled
    assert "drama_scores.analysis_as_of DESC" in compiled
    assert "drama_scores.score_id DESC" in compiled
    assert statement._limit_clause.value == 1


def test_get_latest_score_date_and_no_data_return_none() -> None:
    session = make_session()
    repository = ScoreRepository(session)
    session.scalar.return_value = SCORE_DATE

    assert repository.get_latest_score_date(
        algorithm_version=VERSION,
        score_scope_type="ALL",
        score_scope_id=0,
    ) == SCORE_DATE

    session.scalar.return_value = None
    assert repository.get_latest_score_date(
        algorithm_version=VERSION,
        score_scope_type="ALL",
        score_scope_id=0,
    ) is None


def test_get_level_distribution_fills_missing_levels_and_handles_no_data() -> None:
    session = make_session()
    repository = ScoreRepository(session)
    session.execute.return_value.all.return_value = [("S", 2), ("B", 3)]

    distribution = repository.get_level_distribution(
        score_date=SCORE_DATE,
        algorithm_version=VERSION,
        score_scope_type="ALL",
        score_scope_id=0,
    )

    assert distribution == {"S": 2, "A": 0, "B": 3, "C": 0}
    statement = session.execute.call_args.args[0]
    compiled = str(statement.compile(dialect=dialect()))
    assert "count(drama_scores.score_id)" in compiled
    assert "GROUP BY drama_scores.level" in compiled

    session.execute.return_value.all.return_value = []
    assert repository.get_level_distribution(
        score_date=SCORE_DATE,
        algorithm_version=VERSION,
        score_scope_type="ALL",
        score_scope_id=0,
    ) == {"S": 0, "A": 0, "B": 0, "C": 0}
    session.commit.assert_not_called()


def test_ranking_empty_page_is_preserved() -> None:
    session = make_session()
    session.scalar.return_value = 0
    session.scalars.return_value.all.return_value = []

    page = ScoreRepository(session).paginate_ranking(
        score_date=SCORE_DATE,
        algorithm_version=VERSION,
        score_scope_type="ALL",
        score_scope_id=0,
        page=1,
        page_size=20,
    )

    assert page.total == 0
    assert page.items == []
    session.commit.assert_not_called()
