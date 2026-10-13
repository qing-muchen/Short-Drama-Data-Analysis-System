"""DataQualityService orchestration, transaction, and delegation tests."""

from datetime import UTC, date, datetime
from decimal import Decimal
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, create_autospec

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from analytics.data_quality import (
    QUALITY_SCORE_VERSION,
    QUALITY_SCORE_V2_VERSION,
    DataQualityCalculationError,
    DataQualityScoreResult,
    calculate_data_quality_score,
)
from analytics.data_quality_rules import production_evaluator_registry
from repositories.data_quality_evidence_repository import QualityEvidenceBundle
from repositories.data_quality_repository import (
    DataQualityRuleRepository,
    DataQualityRuleResultRepository,
    DataQualityScoreRepository,
)
from repositories.import_repository import OperationLogRepository
from services.data_quality_service import (
    CURRENT_RULE_SET_VERSION,
    QUALITY_SCOPE_ID,
    QUALITY_SCOPE_TYPE,
    DataQualityRuleExecutionError,
    DataQualityService,
    RuleExecutionResult,
)
from services.exceptions import PersistenceException, ValidationException
from services.data_quality_rule_seed import APPROVED_RULE_DEFINITIONS

SCORE_DATE = date(2026, 9, 16)
NOW = datetime(2026, 9, 16, 12, 30, tzinfo=UTC)


def _rule(
    rule_id: int,
    *,
    code: str,
    dimension: str,
    evaluator_key: str,
    scoring_method: str = "PASS_RATE",
    weight: str = "1.000000",
) -> SimpleNamespace:
    return SimpleNamespace(
        quality_rule_id=rule_id,
        rule_code=code,
        rule_version="1.0",
        dimension=dimension,
        target_entity_type="DRAMA",
        evaluator_key=evaluator_key,
        scoring_method=scoring_method,
        weight=Decimal(weight),
        configuration={"field": code.lower()},
    )


def _rules() -> list[SimpleNamespace]:
    return [
        _rule(
            1,
            code="DQ_COMPLETENESS",
            dimension="COMPLETENESS",
            evaluator_key="required_field",
        ),
        _rule(
            2,
            code="DQ_ACCURACY",
            dimension="ACCURACY",
            evaluator_key="numeric_range",
        ),
        _rule(
            3,
            code="DQ_CONSISTENCY",
            dimension="CONSISTENCY",
            evaluator_key="relation_consistency",
        ),
        _rule(
            4,
            code="DQ_TIMELINESS",
            dimension="TIMELINESS",
            evaluator_key="snapshot_freshness",
            scoring_method="BUCKET_AVERAGE",
        ),
    ]


def _applied_result(*, score: str | None = None) -> RuleExecutionResult:
    return RuleExecutionResult(
        status="PASS",
        applicable_count=10,
        passed_count=10,
        failed_count=0,
        rule_score=Decimal(score) if score is not None else None,
        evidence_summary="10 records evaluated",
    )


def _calculated_score() -> DataQualityScoreResult:
    return DataQualityScoreResult(
        completeness_score=Decimal("100.00"),
        accuracy_score=Decimal("100.00"),
        consistency_score=Decimal("100.00"),
        timeliness_score=Decimal("100.00"),
        total_score=Decimal("100.00"),
        quality_grade="S",
        rule_set_version=CURRENT_RULE_SET_VERSION,
    )


def _service() -> tuple[
    DataQualityService,
    Session,
    DataQualityRuleRepository,
    DataQualityRuleResultRepository,
    DataQualityScoreRepository,
    OperationLogRepository,
    dict[str, MagicMock],
    MagicMock,
]:
    session = create_autospec(Session, instance=True)
    rules = DataQualityRuleRepository(session)
    rule_results = DataQualityRuleResultRepository(session)
    scores = DataQualityScoreRepository(session)
    operation_logs = OperationLogRepository(session)
    rules.list_effective_rules = MagicMock(return_value=_rules())
    rule_results.bulk_create = MagicMock(return_value=[])
    scores.replace_scope_scores = MagicMock(
        return_value=[SimpleNamespace(quality_score_id=41)]
    )
    scores.get_by_identity = MagicMock(return_value=None)
    scores.get_current_score = MagicMock()
    scores.list_history = MagicMock(return_value=[])
    operation_logs.create = MagicMock()
    evaluators = {
        "required_field": MagicMock(return_value=_applied_result()),
        "numeric_range": MagicMock(return_value=_applied_result()),
        "relation_consistency": MagicMock(return_value=_applied_result()),
        "snapshot_freshness": MagicMock(return_value=_applied_result(score="100.00")),
    }
    calculator = MagicMock(return_value=_calculated_score())
    service = DataQualityService(
        session,
        rules,
        rule_results,
        scores,
        operation_logs,
        evaluators,
        calculator=calculator,
    )
    service.evidence.load_bundle = MagicMock(
        return_value=SimpleNamespace(source_watermark={"replay_capability": "LIMITED_CURRENT_MASTER"})
    )
    return (
        service,
        session,
        rules,
        rule_results,
        scores,
        operation_logs,
        evaluators,
        calculator,
    )


def test_normal_quality_calculation_runs_complete_pipeline_once() -> None:
    (
        service,
        session,
        rules,
        rule_results,
        scores,
        operation_logs,
        evaluators,
        calculator,
    ) = _service()

    result = service.calculate_quality_score(
        SCORE_DATE,
        administrator_id=7,
        now=NOW,
        request_id="quality-request-1",
        algorithm_version=QUALITY_SCORE_VERSION,
    )

    rules.list_effective_rules.assert_called_once_with(
        as_of=datetime(2026, 9, 16, 12, 30),
        status="ACTIVE",
    )
    assert all(evaluator.call_count == 1 for evaluator in evaluators.values())
    calculator.assert_called_once()
    calculator_inputs = calculator.call_args.args[0]
    assert len(calculator_inputs) == 4
    assert {item.dimension for item in calculator_inputs} == {
        "COMPLETENESS", "ACCURACY", "CONSISTENCY", "TIMELINESS"
    }
    assert calculator.call_args.kwargs == {"rule_set_version": CURRENT_RULE_SET_VERSION}
    score_call = scores.replace_scope_scores.call_args.kwargs
    assert score_call["score_date"] == SCORE_DATE
    assert score_call["rule_set_version"] == CURRENT_RULE_SET_VERSION
    assert score_call["score_scope_type"] == QUALITY_SCOPE_TYPE
    assert score_call["score_scope_id"] == QUALITY_SCOPE_ID
    assert len(score_call["scores"]) == 1
    assert score_call["algorithm_version"] == QUALITY_SCORE_VERSION
    assert len(score_call["rule_set_hash"]) == 64
    result_call = rule_results.bulk_create.call_args.kwargs
    assert result_call["quality_score_id"] == 41
    assert len(result_call["results"]) == 4
    assert all(item["result_status"] == "APPLIED" for item in result_call["results"])
    assert all(item["rule_score"] == Decimal("100.00") for item in result_call["results"])
    operation_logs.create.assert_called_once()
    audit = operation_logs.create.call_args.args[0]
    assert audit["operation_type"] == "QUALITY_SCORE_CALCULATE"
    assert audit["request_id"] == "quality-request-1"
    detail = json.loads(audit["summary"])
    assert detail["scope"] == {"type": "ALL", "id": 0}
    assert detail["rule_count"] == 4
    assert result.quality_score_id == 41
    assert result.total_score == Decimal("100.00")
    assert result.rule_count == 4
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()


def test_service_integrates_with_real_quality_calculator() -> None:
    service, session, _, rule_results, scores, _, _, _ = _service()
    service.calculator = calculate_data_quality_score

    result = service.calculate_quality_score(
        SCORE_DATE,
        administrator_id=7,
        now=NOW,
        algorithm_version=QUALITY_SCORE_VERSION,
    )

    assert result.total_score == Decimal("100.00")
    assert result.quality_grade == "S"
    assert scores.replace_scope_scores.call_args.kwargs["scores"][0][
        "total_score"
    ] == Decimal("100.00")
    assert len(rule_results.bulk_create.call_args.kwargs["results"]) == 4
    session.commit.assert_called_once_with()


def test_v2_persists_rule_score_algorithm_and_limited_master_watermark() -> None:
    service, session, _, rule_results, scores, _, _, _ = _service()

    result = service.calculate_quality_score(
        SCORE_DATE,
        administrator_id=7,
        now=NOW,
        algorithm_version=QUALITY_SCORE_V2_VERSION,
    )

    score_call = scores.replace_scope_scores.call_args.kwargs
    assert result.algorithm_version == QUALITY_SCORE_V2_VERSION
    assert score_call["algorithm_version"] == QUALITY_SCORE_V2_VERSION
    assert score_call["scores"][0]["source_watermark"] == {
        "replay_capability": "LIMITED_CURRENT_MASTER"
    }
    assert len(rule_results.bulk_create.call_args.kwargs["results"]) == 4
    session.commit.assert_called_once_with()


def test_no_active_rules_rolls_back_without_partial_writes() -> None:
    service, session, rules, rule_results, scores, logs, _, calculator = _service()
    rules.list_effective_rules.return_value = []
    with pytest.raises(ValidationException) as error:
        service.calculate_quality_score(SCORE_DATE, administrator_id=7, now=NOW, algorithm_version=QUALITY_SCORE_VERSION)
    assert error.value.details == {"reason": "NO_ACTIVE_RULE_SET"}
    calculator.assert_not_called()
    scores.replace_scope_scores.assert_not_called()
    rule_results.bulk_create.assert_not_called()
    logs.create.assert_not_called()
    session.rollback.assert_called_once_with()


def test_no_eligible_feed_stops_scoring_without_persistence() -> None:
    service, session, rules, rule_results, scores, logs, _, _ = _service()
    rules.list_effective_rules.return_value = [
        SimpleNamespace(quality_rule_id=index, **dict(definition))
        for index, definition in enumerate(APPROVED_RULE_DEFINITIONS, start=1)
    ]
    service.rule_evaluators = dict(production_evaluator_registry())
    service.evidence.load_bundle.return_value = QualityEvidenceBundle(
        score_date=SCORE_DATE,
        analysis_as_of=datetime(2026, 9, 16, 12, 30),
        window_start=datetime(2026, 9, 8, 16),
        window_end=datetime(2026, 9, 15, 16),
        eligible_feeds=(),
        window_slots=(),
        latest_valid_slot_by_feed={},
        source_watermark={"replay_capability": "LIMITED_CURRENT_MASTER"},
    )

    with pytest.raises(ValidationException) as error:
        service.calculate_quality_score(
            SCORE_DATE,
            administrator_id=7,
            now=NOW,
            algorithm_version=QUALITY_SCORE_V2_VERSION,
        )

    assert error.value.details == {"reason": "INSUFFICIENT_QUALITY_DATA"}
    scores.replace_scope_scores.assert_not_called()
    rule_results.bulk_create.assert_not_called()
    logs.create.assert_not_called()
    session.rollback.assert_called_once_with()


def test_rule_execution_failure_rolls_back_and_stops_pipeline() -> None:
    service, session, _, rule_results, scores, logs, evaluators, calculator = _service()
    evaluators["required_field"].side_effect = RuntimeError("evidence failed")
    with pytest.raises(DataQualityRuleExecutionError) as error:
        service.calculate_quality_score(SCORE_DATE, administrator_id=7, now=NOW, algorithm_version=QUALITY_SCORE_VERSION)
    assert error.value.rule_code == "DQ_COMPLETENESS"
    calculator.assert_not_called()
    scores.replace_scope_scores.assert_not_called()
    rule_results.bulk_create.assert_not_called()
    logs.create.assert_not_called()
    session.rollback.assert_called_once_with()


def test_calculator_failure_rolls_back_without_persistence() -> None:
    service, session, _, rule_results, scores, logs, _, calculator = _service()
    calculator.side_effect = DataQualityCalculationError(
        "INSUFFICIENT_QUALITY_DATA",
        "missing dimension",
    )
    with pytest.raises(ValidationException) as error:
        service.calculate_quality_score(SCORE_DATE, administrator_id=7, now=NOW, algorithm_version=QUALITY_SCORE_VERSION)
    assert error.value.details == {"reason": "INSUFFICIENT_QUALITY_DATA"}
    scores.replace_scope_scores.assert_not_called()
    rule_results.bulk_create.assert_not_called()
    logs.create.assert_not_called()
    session.rollback.assert_called_once_with()


@pytest.mark.parametrize("failing_stage", ["score", "rule_result"])
def test_repository_failure_rolls_back_entire_transaction(failing_stage: str) -> None:
    service, session, _, rule_results, scores, logs, _, _ = _service()
    if failing_stage == "score":
        scores.replace_scope_scores.side_effect = SQLAlchemyError("score write")
    else:
        rule_results.bulk_create.side_effect = SQLAlchemyError("result write")
    with pytest.raises(PersistenceException):
        service.calculate_quality_score(SCORE_DATE, administrator_id=7, now=NOW, algorithm_version=QUALITY_SCORE_VERSION)
    logs.create.assert_not_called()
    session.rollback.assert_called_once_with()


def test_operation_log_failure_rolls_back_score_and_rule_results() -> None:
    service, session, _, rule_results, scores, logs, _, _ = _service()
    logs.create.side_effect = SQLAlchemyError("audit write")
    with pytest.raises(PersistenceException):
        service.calculate_quality_score(SCORE_DATE, administrator_id=7, now=NOW, algorithm_version=QUALITY_SCORE_VERSION)
    scores.replace_scope_scores.assert_called_once()
    rule_results.bulk_create.assert_called_once()
    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


def test_repeated_calculation_returns_existing_identity_without_rewriting() -> None:
    service, session, _, _, scores, logs, _, _ = _service()
    persisted = SimpleNamespace(
        quality_score_id=41,
        score_date=SCORE_DATE,
        analysis_as_of=datetime(2026, 9, 16, 12, 30),
        algorithm_version=QUALITY_SCORE_VERSION,
        rule_set_version=CURRENT_RULE_SET_VERSION,
        rule_set_hash="a" * 64,
        score_scope_type="ALL",
        score_scope_id=0,
        evaluated_entity_count=10,
        total_score=Decimal("100.00"),
        quality_grade="S",
        rule_results=[SimpleNamespace(result_status="APPLIED") for _ in range(4)],
    )
    scores.get_by_identity.side_effect = [None, persisted]
    first = service.calculate_quality_score(SCORE_DATE, administrator_id=7, now=NOW, algorithm_version=QUALITY_SCORE_VERSION)
    second = service.calculate_quality_score(SCORE_DATE, administrator_id=7, now=NOW, algorithm_version=QUALITY_SCORE_VERSION)
    assert (first.quality_score_id, second.quality_score_id) == (41, 41)
    assert scores.replace_scope_scores.call_count == 1
    for call in scores.replace_scope_scores.call_args_list:
        assert call.kwargs["rule_set_version"] == CURRENT_RULE_SET_VERSION
        assert call.kwargs["score_scope_type"] == "ALL"
        assert call.kwargs["score_scope_id"] == 0
    assert logs.create.call_count == 1
    assert session.commit.call_count == 2


def test_not_applicable_rule_is_persisted_but_excluded_from_calculator() -> None:
    service, session, rules, rule_results, _, _, evaluators, calculator = _service()
    optional = _rule(
        5,
        code="DQ_OPTIONAL",
        dimension="COMPLETENESS",
        evaluator_key="optional_check",
        weight="0.100000",
    )
    rules.list_effective_rules.return_value = [*_rules(), optional]
    evaluators["optional_check"] = MagicMock(return_value=RuleExecutionResult(
        status="NOT_APPLICABLE", applicable_count=0, passed_count=0, failed_count=0,
        not_applicable_reason="No eligible source records",
    ))
    service.rule_evaluators["optional_check"] = evaluators["optional_check"]
    result = service.calculate_quality_score(SCORE_DATE, administrator_id=7, now=NOW, algorithm_version=QUALITY_SCORE_VERSION)
    assert len(calculator.call_args.args[0]) == 4
    persisted = rule_results.bulk_create.call_args.kwargs["results"]
    assert persisted[-1]["result_status"] == "NOT_APPLICABLE"
    assert result.not_applicable_rule_count == 1
    session.commit.assert_called_once_with()


def test_invalid_rule_result_is_treated_as_rule_execution_failure() -> None:
    service, session, _, _, scores, _, evaluators, _ = _service()
    evaluators["numeric_range"].return_value = RuleExecutionResult(
        status="FAIL", applicable_count=10, passed_count=9, failed_count=0
    )
    with pytest.raises(DataQualityRuleExecutionError):
        service.calculate_quality_score(SCORE_DATE, administrator_id=7, now=NOW, algorithm_version=QUALITY_SCORE_VERSION)
    scores.replace_scope_scores.assert_not_called()
    session.rollback.assert_called_once_with()


def test_rule_set_hash_is_deterministic_for_rule_order() -> None:
    service, _, rules, _, scores, _, _, _ = _service()
    service.calculate_quality_score(SCORE_DATE, administrator_id=7, now=NOW, algorithm_version=QUALITY_SCORE_VERSION)
    first_hash = scores.replace_scope_scores.call_args.kwargs["rule_set_hash"]
    scores.replace_scope_scores.reset_mock()
    rules.list_effective_rules.return_value = list(reversed(_rules()))
    service.calculate_quality_score(SCORE_DATE, administrator_id=7, now=NOW, algorithm_version=QUALITY_SCORE_VERSION)
    second_hash = scores.replace_scope_scores.call_args.kwargs["rule_set_hash"]
    assert first_hash == second_hash


def test_queries_delegate_with_fixed_scope_without_recalculation() -> None:
    service, _, rules, _, scores, _, evaluators, calculator = _service()
    current = SimpleNamespace(quality_score_id=41)
    history = [SimpleNamespace(quality_score_id=40)]
    scores.get_current_score.return_value = current
    scores.list_history.return_value = history
    assert service.get_current_quality_score(
        algorithm_version=QUALITY_SCORE_VERSION
    ) is current
    assert service.get_quality_history(
        start_date=date(2026, 9, 1),
        end_date=SCORE_DATE,
        limit=30,
        algorithm_version=QUALITY_SCORE_VERSION,
    ) == history
    scores.get_current_score.assert_called_once_with(
        score_scope_type="ALL", score_scope_id=0,
        algorithm_version=QUALITY_SCORE_VERSION,
        rule_set_version=CURRENT_RULE_SET_VERSION,
    )
    scores.list_history.assert_called_once_with(
        score_scope_type="ALL", score_scope_id=0,
        algorithm_version=QUALITY_SCORE_VERSION,
        rule_set_version=CURRENT_RULE_SET_VERSION,
        start_date=date(2026, 9, 1), end_date=SCORE_DATE, limit=30,
    )
    rules.list_effective_rules.assert_not_called()
    calculator.assert_not_called()
    assert all(evaluator.call_count == 0 for evaluator in evaluators.values())


def test_current_rules_are_available_before_any_score_exists() -> None:
    service, _, rules, _, scores, _, _, _ = _service()
    current = service.get_current_quality_rules(now=NOW)

    assert current.rule_set_version == CURRENT_RULE_SET_VERSION
    assert len(current.rule_set_hash or "") == 64
    assert len(current.rules) == 4
    scores.get_current_score.assert_not_called()
    rules.list_effective_rules.assert_called_once_with(
        as_of=datetime(2026, 9, 16, 12, 30),
        status="ACTIVE",
    )


def test_future_score_date_is_rejected_before_repository_access() -> None:
    service, session, rules, _, scores, logs, _, _ = _service()
    with pytest.raises(ValidationException):
        service.calculate_quality_score(date(2026, 9, 17), administrator_id=7, now=NOW, algorithm_version=QUALITY_SCORE_VERSION)
    rules.list_effective_rules.assert_not_called()
    scores.replace_scope_scores.assert_not_called()
    logs.create.assert_not_called()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()
