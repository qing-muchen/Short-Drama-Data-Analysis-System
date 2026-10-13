"""Explicit DQ rule seed check/apply, conflict, and rollback tests."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, create_autospec

import pytest
from sqlalchemy.orm import Session

from models.data_quality import DataQualityRule
from models.operation_log import OperationLog
from services.data_quality_rule_seed import (
    APPROVED_RULE_DEFINITIONS,
    DataQualityRuleSeedConflict,
    seed_data_quality_rules,
)

VALID_FROM = datetime(2026, 10, 15, 0, 0)


def _session(existing: list[object] | None = None) -> Session:
    session = create_autospec(Session, instance=True)
    session.scalars.return_value.all.return_value = existing or []
    return session


def _existing_rule(definition: object) -> SimpleNamespace:
    values = dict(definition)  # type: ignore[arg-type]
    values.update(valid_from=VALID_FROM, valid_to=None)
    return SimpleNamespace(**values)


def test_seed_check_is_read_only_and_reports_four_missing_rules() -> None:
    session = _session()
    result = seed_data_quality_rules(session, valid_from=VALID_FROM)

    assert result.mode == "CHECK"
    assert result.inserted_count == 0
    assert result.unchanged_count == 0
    assert len(result.configuration_hash) == 64
    session.add_all.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()


def test_seed_apply_inserts_four_rules_and_one_audit_event_atomically() -> None:
    session = _session()
    result = seed_data_quality_rules(
        session,
        valid_from=VALID_FROM,
        apply=True,
        actor_user_id=7,
    )

    seeded = tuple(session.add_all.call_args.args[0])
    assert len(seeded) == 4
    assert all(isinstance(item, DataQualityRule) for item in seeded)
    assert {item.rule_code for item in seeded} == {
        "DQ_C_PLAY_COUNT_COVERAGE",
        "DQ_A_CUMULATIVE_NONNEGATIVE",
        "DQ_K_REVISION_CHAIN_VALID",
        "DQ_T_SNAPSHOT_FRESHNESS",
    }
    assert isinstance(session.add.call_args.args[0], OperationLog)
    assert result.inserted_count == 4
    assert session.flush.call_count == 2
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()


def test_seed_second_apply_is_rule_idempotent_and_writes_nothing() -> None:
    existing = [_existing_rule(item) for item in APPROVED_RULE_DEFINITIONS]
    session = _session(existing)
    result = seed_data_quality_rules(
        session,
        valid_from=VALID_FROM,
        apply=True,
        actor_user_id=7,
    )

    assert result.inserted_count == 0
    assert result.unchanged_count == 4
    session.add_all.assert_not_called()
    session.add.assert_not_called()
    session.commit.assert_called_once_with()


def test_seed_conflict_rolls_back_without_overwriting_history() -> None:
    conflicting = _existing_rule(APPROVED_RULE_DEFINITIONS[0])
    conflicting.weight = 0.5
    session = _session([conflicting])

    with pytest.raises(DataQualityRuleSeedConflict):
        seed_data_quality_rules(
            session,
            valid_from=VALID_FROM,
            apply=True,
            actor_user_id=7,
        )

    session.add_all.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()


def test_seed_apply_requires_explicit_actor() -> None:
    session = _session()
    with pytest.raises(ValueError):
        seed_data_quality_rules(session, valid_from=VALID_FROM, apply=True)
    session.add_all.assert_not_called()
