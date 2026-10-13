"""Data-quality rule orchestration and atomic persistence for Phase 2 V1."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
import json
from typing import Any, Literal, Protocol
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from analytics.data_quality import (
    QUALITY_SCORE_VERSION,
    QUALITY_SCORE_V2_VERSION,
    DataQualityCalculationError,
    DataQualityScoreResult,
    QualityRuleResult,
    ScoredQualityRuleResult,
    calculate_data_quality_score,
    calculate_data_quality_score_v2,
    calculate_rule_pass_rate,
)
from repositories.data_quality_evidence_repository import (
    DataQualityEvidenceRepository,
    QualityEvidenceBundle,
)
from repositories.data_quality_repository import (
    DataQualityRuleRepository,
    DataQualityRuleResultRepository,
    DataQualityScoreRepository,
)
from repositories.import_repository import OperationLogRepository
from services.base import BaseService
from services.exceptions import ValidationException

QUALITY_SCOPE_TYPE = "ALL"
QUALITY_SCOPE_ID = 0
CURRENT_RULE_SET_VERSION = "DQ Rules 1.0"
CURRENT_ALGORITHM_VERSION = QUALITY_SCORE_V2_VERSION
BUSINESS_TIME_ZONE = ZoneInfo("Asia/Shanghai")

RuleOutcome = Literal["PASS", "FAIL", "NOT_APPLICABLE"]
QualityCalculator = Callable[..., DataQualityScoreResult]


@dataclass(frozen=True, slots=True)
class QualityEvaluationContext:
    """Transport-neutral context supplied to every registered rule evaluator."""

    score_date: date
    analysis_as_of: datetime
    score_scope_type: str = QUALITY_SCOPE_TYPE
    score_scope_id: int = QUALITY_SCOPE_ID


@dataclass(frozen=True, slots=True)
class RuleExecutionResult:
    """One evaluator outcome before persistence mapping and score aggregation."""

    status: RuleOutcome
    applicable_count: int
    passed_count: int
    failed_count: int
    rule_score: Decimal | int | float | None = None
    not_applicable_reason: str | None = None
    evidence_summary: str | None = None


class RuleEvaluator(Protocol):
    """Callable contract for a whitelisted pure evaluator implementation."""

    def __call__(
        self,
        rule: Any,
        context: QualityEvaluationContext,
        evidence: QualityEvidenceBundle,
        /,
    ) -> RuleExecutionResult: ...


class DataQualityRuleExecutionError(RuntimeError):
    """Report a stable rule-execution failure without persistence coupling."""

    code = "QUALITY_RULE_EXECUTION_FAILED"

    def __init__(self, rule_code: str, message: str) -> None:
        self.rule_code = rule_code
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class QualityScoreCalculationResult:
    """Summary returned after one atomic quality-score calculation."""

    quality_score_id: int
    score_date: date
    analysis_as_of: datetime
    algorithm_version: str
    rule_set_version: str
    rule_set_hash: str
    score_scope_type: str
    score_scope_id: int
    rule_count: int
    applied_rule_count: int
    not_applicable_rule_count: int
    evaluated_entity_count: int
    total_score: Decimal
    quality_grade: str


@dataclass(frozen=True, slots=True)
class CurrentQualityRuleSet:
    rule_set_version: str
    rule_set_hash: str | None
    rules: tuple[Any, ...]


@dataclass(frozen=True, slots=True)
class _PreparedRuleResult:
    v1_calculator_input: QualityRuleResult | None
    v2_calculator_input: ScoredQualityRuleResult | None
    persistence_values: dict[str, Any]
    applicable_count: int


class DataQualityService(BaseService):
    """Load rules, execute evaluators, calculate, persist, and audit atomically."""

    def __init__(
        self,
        session: Session,
        rules: DataQualityRuleRepository,
        rule_results: DataQualityRuleResultRepository,
        scores: DataQualityScoreRepository,
        operation_logs: OperationLogRepository,
        rule_evaluators: Mapping[str, RuleEvaluator],
        *,
        evidence: DataQualityEvidenceRepository | None = None,
        calculator: QualityCalculator = calculate_data_quality_score,
        v2_calculator: QualityCalculator = calculate_data_quality_score_v2,
    ) -> None:
        evidence_repository = evidence or DataQualityEvidenceRepository(session)
        super().__init__(
            session,
            rules,
            rule_results,
            scores,
            operation_logs,
            evidence_repository,
        )
        self.rules = rules
        self.rule_results = rule_results
        self.scores = scores
        self.operation_logs = operation_logs
        self.evidence = evidence_repository
        self.rule_evaluators = dict(rule_evaluators)
        self.calculator = calculator
        self.v2_calculator = v2_calculator

    def calculate_quality_score(
        self,
        score_date: date,
        *,
        administrator_id: int,
        algorithm_version: str = CURRENT_ALGORITHM_VERSION,
        now: datetime | None = None,
        request_id: str | None = None,
    ) -> QualityScoreCalculationResult:
        """Calculate one versioned score and persist its evidence atomically."""

        if algorithm_version not in {QUALITY_SCORE_VERSION, QUALITY_SCORE_V2_VERSION}:
            raise ValidationException(
                "Unsupported data-quality algorithm version",
                details={"reason": "UNSUPPORTED_ALGORITHM_VERSION"},
            )

        analysis_as_of = _resolve_analysis_as_of(score_date, now=now)
        context = QualityEvaluationContext(
            score_date=score_date,
            analysis_as_of=analysis_as_of,
        )

        with self.transaction():
            active_rules = self.rules.list_effective_rules(
                as_of=analysis_as_of,
                status="ACTIVE",
            )
            if not active_rules:
                raise ValidationException(
                    "No active data-quality rules are available",
                    details={"reason": "NO_ACTIVE_RULE_SET"},
                )

            rule_set_hash = _calculate_rule_set_hash(active_rules)
            existing = self.scores.get_by_identity(
                score_date=score_date,
                algorithm_version=algorithm_version,
                rule_set_version=CURRENT_RULE_SET_VERSION,
                rule_set_hash=rule_set_hash,
                score_scope_type=QUALITY_SCOPE_TYPE,
                score_scope_id=QUALITY_SCOPE_ID,
            )
            if existing is not None:
                return _calculation_result_from_entity(existing)
            evidence = self.evidence.load_bundle(
                score_date=score_date,
                analysis_as_of=analysis_as_of,
            )
            prepared = [
                self._execute_rule(rule, context=context, evidence=evidence)
                for rule in active_rules
            ]
            try:
                if algorithm_version == QUALITY_SCORE_VERSION:
                    calculator_inputs = [
                        item.v1_calculator_input
                        for item in prepared
                        if item.v1_calculator_input is not None
                    ]
                    if not calculator_inputs:
                        raise DataQualityCalculationError(
                            "INSUFFICIENT_QUALITY_DATA",
                            "no data-quality rule is applicable",
                        )
                    calculated = self.calculator(
                        calculator_inputs,
                        rule_set_version=CURRENT_RULE_SET_VERSION,
                    )
                else:
                    scored_inputs = [
                        item.v2_calculator_input
                        for item in prepared
                        if item.v2_calculator_input is not None
                    ]
                    if not scored_inputs:
                        raise DataQualityCalculationError(
                            "INSUFFICIENT_QUALITY_DATA",
                            "no data-quality rule is applicable",
                        )
                    calculated = self.v2_calculator(
                        scored_inputs,
                        rule_set_version=CURRENT_RULE_SET_VERSION,
                    )
            except DataQualityCalculationError as error:
                raise ValidationException(
                    "Insufficient applicable data-quality evidence",
                    details={"reason": error.code},
                ) from error
            evaluated_entity_count = max(
                (item.applicable_count for item in prepared),
                default=0,
            )

            score_entities = self.scores.replace_scope_scores(
                score_date=score_date,
                rule_set_version=CURRENT_RULE_SET_VERSION,
                algorithm_version=calculated.algorithm_version,
                rule_set_hash=rule_set_hash,
                score_scope_type=QUALITY_SCOPE_TYPE,
                score_scope_id=QUALITY_SCOPE_ID,
                scores=[
                    {
                        "analysis_as_of": analysis_as_of,
                        "completeness_score": calculated.completeness_score,
                        "accuracy_score": calculated.accuracy_score,
                        "consistency_score": calculated.consistency_score,
                        "timeliness_score": calculated.timeliness_score,
                        "total_score": calculated.total_score,
                        "quality_grade": calculated.quality_grade,
                        "evaluated_entity_count": evaluated_entity_count,
                        "open_issue_count": 0,
                        "source_watermark": dict(evidence.source_watermark),
                    }
                ],
            )
            if len(score_entities) != 1:
                raise RuntimeError(
                    "Quality score replacement must return exactly one entity"
                )
            quality_score_id = int(score_entities[0].quality_score_id)
            self.rule_results.bulk_create(
                quality_score_id=quality_score_id,
                results=[item.persistence_values for item in prepared],
            )
            self._audit_calculation(
                administrator_id=administrator_id,
                request_id=request_id,
                score_date=score_date,
                calculated=calculated,
                rule_set_hash=rule_set_hash,
                prepared=prepared,
                evaluated_entity_count=evaluated_entity_count,
            )

        applied_count = sum(
            item.v1_calculator_input is not None for item in prepared
        )
        return QualityScoreCalculationResult(
            quality_score_id=quality_score_id,
            score_date=score_date,
            analysis_as_of=analysis_as_of,
            algorithm_version=calculated.algorithm_version,
            rule_set_version=CURRENT_RULE_SET_VERSION,
            rule_set_hash=rule_set_hash,
            score_scope_type=QUALITY_SCOPE_TYPE,
            score_scope_id=QUALITY_SCOPE_ID,
            rule_count=len(prepared),
            applied_rule_count=applied_count,
            not_applicable_rule_count=len(prepared) - applied_count,
            evaluated_entity_count=evaluated_entity_count,
            total_score=calculated.total_score,
            quality_grade=calculated.quality_grade,
        )

    def get_current_quality_score(
        self,
        *,
        algorithm_version: str = CURRENT_ALGORITHM_VERSION,
        rule_set_version: str = CURRENT_RULE_SET_VERSION,
    ) -> Any | None:
        """Delegate current fixed-scope lookup without recalculation."""

        return self.read(
            self.scores.get_current_score,
            score_scope_type=QUALITY_SCOPE_TYPE,
            score_scope_id=QUALITY_SCOPE_ID,
            algorithm_version=algorithm_version,
            rule_set_version=rule_set_version,
        )

    def get_quality_history(
        self,
        *,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 90,
        algorithm_version: str = CURRENT_ALGORITHM_VERSION,
        rule_set_version: str = CURRENT_RULE_SET_VERSION,
    ) -> list[Any]:
        """Delegate persisted trend lookup without calculation or sorting."""

        return self.read(
            self.scores.list_history,
            score_scope_type=QUALITY_SCOPE_TYPE,
            score_scope_id=QUALITY_SCOPE_ID,
            algorithm_version=algorithm_version,
            rule_set_version=rule_set_version,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )

    def get_current_quality_rules(
        self,
        *,
        now: datetime | None = None,
    ) -> CurrentQualityRuleSet:
        """Return currently effective reviewed rules without requiring a score."""

        current = now or datetime.now(UTC)
        if current.tzinfo is not None and current.utcoffset() is not None:
            current = current.astimezone(UTC).replace(tzinfo=None)
        rules = tuple(
            self.read(
                self.rules.list_effective_rules,
                as_of=current,
                status="ACTIVE",
            )
        )
        return CurrentQualityRuleSet(
            rule_set_version=CURRENT_RULE_SET_VERSION,
            rule_set_hash=_calculate_rule_set_hash(rules) if rules else None,
            rules=rules,
        )

    def _execute_rule(
        self,
        rule: Any,
        *,
        context: QualityEvaluationContext,
        evidence: QualityEvidenceBundle,
    ) -> _PreparedRuleResult:
        evaluator = self.rule_evaluators.get(str(rule.evaluator_key))
        if evaluator is None:
            raise DataQualityRuleExecutionError(
                str(rule.rule_code),
                f"No evaluator is registered for rule {rule.rule_code}",
            )
        try:
            execution = evaluator(rule, context, evidence)
            return _prepare_rule_result(rule, execution)
        except DataQualityRuleExecutionError:
            raise
        except Exception as error:
            raise DataQualityRuleExecutionError(
                str(rule.rule_code),
                f"Rule {rule.rule_code} execution failed",
            ) from error

    def _audit_calculation(
        self,
        *,
        administrator_id: int,
        request_id: str | None,
        score_date: date,
        calculated: DataQualityScoreResult,
        rule_set_hash: str,
        prepared: Sequence[_PreparedRuleResult],
        evaluated_entity_count: int,
    ) -> None:
        applied_count = sum(
            item.v1_calculator_input is not None for item in prepared
        )
        detail = {
            "score_date": score_date.isoformat(),
            "algorithm_version": calculated.algorithm_version,
            "rule_set_version": CURRENT_RULE_SET_VERSION,
            "rule_set_hash": rule_set_hash,
            "scope": {"type": QUALITY_SCOPE_TYPE, "id": QUALITY_SCOPE_ID},
            "rule_count": len(prepared),
            "applied_rule_count": applied_count,
            "not_applicable_rule_count": len(prepared) - applied_count,
            "evaluated_entity_count": evaluated_entity_count,
            "total_score": str(calculated.total_score),
            "quality_grade": calculated.quality_grade,
        }
        values: dict[str, Any] = {
            "actor_user_id": administrator_id,
            "target_user_id": administrator_id,
            "operation_type": "QUALITY_SCORE_CALCULATE",
            "result_status": "SUCCESS",
            "summary": json.dumps(
                detail,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        }
        if request_id is not None:
            values["request_id"] = request_id
        self.operation_logs.create(values)


def _prepare_rule_result(
    rule: Any,
    execution: RuleExecutionResult,
) -> _PreparedRuleResult:
    rule_code = str(rule.rule_code)
    counts = (
        execution.applicable_count,
        execution.passed_count,
        execution.failed_count,
    )
    if any(isinstance(value, bool) or not isinstance(value, int) for value in counts):
        raise DataQualityRuleExecutionError(
            rule_code,
            f"Rule {rule_code} returned non-integer counts",
        )
    if any(value < 0 for value in counts):
        raise DataQualityRuleExecutionError(
            rule_code,
            f"Rule {rule_code} returned negative counts",
        )

    persistence_values: dict[str, Any] = {
        "quality_rule_id": int(rule.quality_rule_id),
        "applicable_count": execution.applicable_count,
        "passed_count": execution.passed_count,
        "failed_count": execution.failed_count,
        "evidence_summary": execution.evidence_summary,
    }
    if execution.status == "NOT_APPLICABLE":
        reason = (execution.not_applicable_reason or "").strip()
        if counts != (0, 0, 0) or not reason:
            raise DataQualityRuleExecutionError(
                rule_code,
                f"Rule {rule_code} returned an invalid NOT_APPLICABLE result",
            )
        persistence_values.update(
            {
                "result_status": "NOT_APPLICABLE",
                "rule_score": None,
                "not_applicable_reason": reason,
            }
        )
        return _PreparedRuleResult(
            v1_calculator_input=None,
            v2_calculator_input=None,
            persistence_values=persistence_values,
            applicable_count=0,
        )

    if execution.status not in {"PASS", "FAIL"}:
        raise DataQualityRuleExecutionError(
            rule_code,
            f"Rule {rule_code} returned an unsupported status",
        )
    if (
        execution.applicable_count <= 0
        or execution.applicable_count
        != execution.passed_count + execution.failed_count
        or execution.not_applicable_reason is not None
    ):
        raise DataQualityRuleExecutionError(
            rule_code,
            f"Rule {rule_code} returned inconsistent applied counts",
        )

    if str(rule.scoring_method) == "PASS_RATE":
        rule_score = calculate_rule_pass_rate(
            pass_count=execution.passed_count,
            total_count=execution.applicable_count,
        )
    elif str(rule.scoring_method) == "BUCKET_AVERAGE":
        rule_score = _validated_rule_score(execution.rule_score, rule_code=rule_code)
    else:
        raise DataQualityRuleExecutionError(
            rule_code,
            f"Rule {rule_code} uses an unsupported scoring method",
        )

    persistence_values.update(
        {
            "result_status": "APPLIED",
            "rule_score": rule_score,
            "not_applicable_reason": None,
        }
    )
    return _PreparedRuleResult(
        v1_calculator_input=QualityRuleResult(
            dimension=str(rule.dimension),
            status=execution.status,
            weight=rule.weight,
        ),
        v2_calculator_input=ScoredQualityRuleResult(
            dimension=str(rule.dimension),
            rule_score=rule_score,
            weight=rule.weight,
        ),
        persistence_values=persistence_values,
        applicable_count=execution.applicable_count,
    )


def _validated_rule_score(
    value: Decimal | int | float | None,
    *,
    rule_code: str,
) -> Decimal:
    if value is None or isinstance(value, bool):
        raise DataQualityRuleExecutionError(
            rule_code,
            f"Rule {rule_code} must provide a bucket-average score",
        )
    try:
        score = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise DataQualityRuleExecutionError(
            rule_code,
            f"Rule {rule_code} returned an invalid score",
        ) from error
    if not score.is_finite() or not Decimal("0") <= score <= Decimal("100"):
        raise DataQualityRuleExecutionError(
            rule_code,
            f"Rule {rule_code} returned a score outside 0..100",
        )
    return score.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _calculation_result_from_entity(entity: Any) -> QualityScoreCalculationResult:
    rule_results = tuple(entity.rule_results)
    applied_count = sum(
        str(item.result_status) == "APPLIED" for item in rule_results
    )
    return QualityScoreCalculationResult(
        quality_score_id=int(entity.quality_score_id),
        score_date=entity.score_date,
        analysis_as_of=entity.analysis_as_of,
        algorithm_version=str(entity.algorithm_version),
        rule_set_version=str(entity.rule_set_version),
        rule_set_hash=str(entity.rule_set_hash),
        score_scope_type=str(entity.score_scope_type),
        score_scope_id=int(entity.score_scope_id),
        rule_count=len(rule_results),
        applied_rule_count=applied_count,
        not_applicable_rule_count=len(rule_results) - applied_count,
        evaluated_entity_count=int(entity.evaluated_entity_count),
        total_score=Decimal(str(entity.total_score)),
        quality_grade=str(entity.quality_grade),
    )


def _calculate_rule_set_hash(rules: Sequence[Any]) -> str:
    canonical_rules = []
    for rule in sorted(
        rules,
        key=lambda item: (
            str(item.rule_code),
            str(item.rule_version),
            int(item.quality_rule_id),
        ),
    ):
        canonical_rules.append(
            {
                "rule_code": str(rule.rule_code),
                "rule_version": str(rule.rule_version),
                "dimension": str(rule.dimension),
                "target_entity_type": str(rule.target_entity_type),
                "evaluator_key": str(rule.evaluator_key),
                "scoring_method": str(rule.scoring_method),
                "weight": format(Decimal(str(rule.weight)), "f"),
                "configuration": rule.configuration,
            }
        )
    payload = json.dumps(
        canonical_rules,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


def _resolve_analysis_as_of(
    score_date: date,
    *,
    now: datetime | None = None,
) -> datetime:
    current = now or datetime.now(BUSINESS_TIME_ZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=BUSINESS_TIME_ZONE)
    else:
        current = current.astimezone(BUSINESS_TIME_ZONE)
    if score_date > current.date():
        raise ValidationException(
            "Quality score date cannot be in the future",
            details={"score_date": score_date.isoformat()},
        )
    local_cutoff = (
        current
        if score_date == current.date()
        else datetime.combine(score_date, time.max, tzinfo=BUSINESS_TIME_ZONE)
    )
    return local_cutoff.astimezone(UTC).replace(tzinfo=None)


__all__ = (
    "CURRENT_ALGORITHM_VERSION",
    "CURRENT_RULE_SET_VERSION",
    "CurrentQualityRuleSet",
    "QUALITY_SCOPE_ID",
    "QUALITY_SCOPE_TYPE",
    "DataQualityRuleExecutionError",
    "DataQualityService",
    "QualityEvaluationContext",
    "QualityScoreCalculationResult",
    "RuleExecutionResult",
    "RuleEvaluator",
)
