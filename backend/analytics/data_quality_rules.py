"""Pure evaluators for the approved DQ Rules 1.0 production subset."""

from __future__ import annotations

from datetime import UTC
from decimal import Decimal, ROUND_HALF_UP, localcontext
import json
from typing import Any, Callable, Mapping

from repositories.data_quality_evidence_repository import (
    BUSINESS_TIME_ZONE,
    QualityEvidenceBundle,
    SnapshotSlotEvidence,
)
from services.data_quality_service import (
    QualityEvaluationContext,
    RuleExecutionResult,
)

Evaluator = Callable[
    [Any, QualityEvaluationContext, QualityEvidenceBundle],
    RuleExecutionResult,
]


def evaluate_play_count_coverage(
    rule: Any,
    context: QualityEvaluationContext,
    evidence: QualityEvidenceBundle,
) -> RuleExecutionResult:
    del context
    if not evidence.eligible_feeds:
        return _not_applicable("NO_ELIGIBLE_FEED")
    expected_days = {
        (evidence.window_start.replace(tzinfo=UTC).astimezone(BUSINESS_TIME_ZONE).date())
    }
    first_day = next(iter(expected_days))
    expected_days = {first_day.fromordinal(first_day.toordinal() + offset) for offset in range(7)}
    passing: set[tuple[int, object]] = set()
    for slot in evidence.window_slots:
        selected = slot.selected_revision
        if (
            selected is not None
            and selected.revision_action != "VOID"
            and selected.play_count is not None
        ):
            local_day = slot.snapshot_time.replace(tzinfo=UTC).astimezone(
                BUSINESS_TIME_ZONE
            ).date()
            if local_day in expected_days:
                passing.add((slot.drama_platform_id, local_day))
    applicable = len(evidence.eligible_feeds) * 7
    passed = len(passing)
    return _pass_rate_result(
        passed=passed,
        applicable=applicable,
        threshold=_threshold(rule),
        summary={
            "eligible_feeds": len(evidence.eligible_feeds),
            "expected_feed_days": applicable,
            "covered_feed_days": passed,
            "limitation": "LIMITED_CURRENT_MASTER",
        },
    )


def evaluate_cumulative_nonnegative(
    rule: Any,
    context: QualityEvaluationContext,
    evidence: QualityEvidenceBundle,
) -> RuleExecutionResult:
    del context
    values: list[int] = []
    for slot in evidence.window_slots:
        selected = slot.selected_revision
        if selected is None or selected.revision_action == "VOID":
            continue
        values.extend(
            value
            for value in (
                selected.play_count,
                selected.like_count,
                selected.comment_count,
                selected.favorite_count,
                selected.share_count,
            )
            if value is not None
        )
    if not values:
        return _not_applicable("NO_CUMULATIVE_METRIC_VALUE")
    passed = sum(value >= 0 for value in values)
    return _pass_rate_result(
        passed=passed,
        applicable=len(values),
        threshold=_threshold(rule),
        summary={
            "evaluated_values": len(values),
            "nonnegative_values": passed,
            "limitation": "LIMITED_CURRENT_MASTER",
        },
    )


def evaluate_revision_chain(
    rule: Any,
    context: QualityEvaluationContext,
    evidence: QualityEvidenceBundle,
) -> RuleExecutionResult:
    del context
    if not evidence.window_slots:
        return _not_applicable("NO_WINDOW_SNAPSHOT")
    passed = sum(_is_complete_chain(slot) for slot in evidence.window_slots)
    return _pass_rate_result(
        passed=passed,
        applicable=len(evidence.window_slots),
        threshold=_threshold(rule),
        summary={
            "window_snapshots": len(evidence.window_slots),
            "valid_revision_chains": passed,
            "void_revisions_included": True,
            "limitation": "LIMITED_CURRENT_MASTER",
        },
    )


def evaluate_snapshot_freshness(
    rule: Any,
    context: QualityEvaluationContext,
    evidence: QualityEvidenceBundle,
) -> RuleExecutionResult:
    if not evidence.eligible_feeds:
        return _not_applicable("NO_ELIGIBLE_FEED")
    bucket_scores: list[Decimal] = []
    passed = 0
    pass_threshold = _threshold(rule)
    for feed in evidence.eligible_feeds:
        slot = evidence.latest_valid_slot_by_feed.get(feed.drama_platform_id)
        score = _freshness_score(
            analysis_as_of=context.analysis_as_of,
            slot=slot,
        )
        bucket_scores.append(score)
        if score >= pass_threshold:
            passed += 1
    with localcontext() as decimal_context:
        decimal_context.prec = 50
        average = (
            sum(bucket_scores, start=Decimal("0")) / Decimal(len(bucket_scores))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return RuleExecutionResult(
        status="PASS" if average >= pass_threshold else "FAIL",
        applicable_count=len(bucket_scores),
        passed_count=passed,
        failed_count=len(bucket_scores) - passed,
        rule_score=average,
        evidence_summary=_summary(
            {
                "eligible_feeds": len(bucket_scores),
                "feeds_at_or_above_threshold": passed,
                "latest_valid_snapshot_required": True,
                "limitation": "LIMITED_CURRENT_MASTER",
            }
        ),
    )


def production_evaluator_registry() -> Mapping[str, Evaluator]:
    """Return the fixed evaluator whitelist for the approved first release."""

    return {
        "play_count_coverage_7d": evaluate_play_count_coverage,
        "cumulative_nonnegative_7d": evaluate_cumulative_nonnegative,
        "revision_chain_valid_7d": evaluate_revision_chain,
        "snapshot_freshness": evaluate_snapshot_freshness,
    }


def _is_complete_chain(slot: SnapshotSlotEvidence) -> bool:
    revisions = sorted(
        slot.visible_revisions,
        key=lambda item: (item.version_no, item.snapshot_revision_id),
    )
    if not revisions:
        return False
    if [item.version_no for item in revisions] != list(range(1, len(revisions) + 1)):
        return False
    first = revisions[0]
    if first.revision_action != "INITIAL" or first.previous_revision_id is not None:
        return False
    for previous, current in zip(revisions, revisions[1:]):
        if (
            current.revision_action not in {"CORRECTION", "VOID"}
            or current.previous_revision_id != previous.snapshot_revision_id
            or current.snapshot_id != slot.snapshot_id
        ):
            return False
    return True


def _freshness_score(
    *,
    analysis_as_of: object,
    slot: SnapshotSlotEvidence | None,
) -> Decimal:
    if slot is None:
        return Decimal("0")
    if not hasattr(analysis_as_of, "__sub__"):
        raise TypeError("analysis_as_of must be a datetime")
    age_seconds = (analysis_as_of - slot.snapshot_time).total_seconds()
    if age_seconds < 0:
        raise ValueError("snapshot_time cannot be later than analysis_as_of")
    age_days = Decimal(str(age_seconds)) / Decimal("86400")
    if age_days <= Decimal("1"):
        return Decimal("100")
    if age_days <= Decimal("2"):
        return Decimal("80")
    if age_days <= Decimal("3"):
        return Decimal("60")
    if age_days <= Decimal("7"):
        return Decimal("40")
    return Decimal("20")


def _threshold(rule: Any) -> Decimal:
    value = rule.configuration.get("pass_threshold")
    if value is None:
        raise ValueError("pass_threshold is required")
    threshold = Decimal(str(value))
    if not threshold.is_finite() or not Decimal("0") <= threshold <= Decimal("100"):
        raise ValueError("pass_threshold must be between 0 and 100")
    return threshold


def _pass_rate_result(
    *,
    passed: int,
    applicable: int,
    threshold: Decimal,
    summary: Mapping[str, object],
) -> RuleExecutionResult:
    with localcontext() as context:
        context.prec = 50
        score = (Decimal(passed) / Decimal(applicable) * Decimal("100")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    return RuleExecutionResult(
        status="PASS" if score >= threshold else "FAIL",
        applicable_count=applicable,
        passed_count=passed,
        failed_count=applicable - passed,
        rule_score=score,
        evidence_summary=_summary(summary),
    )


def _not_applicable(reason: str) -> RuleExecutionResult:
    return RuleExecutionResult(
        status="NOT_APPLICABLE",
        applicable_count=0,
        passed_count=0,
        failed_count=0,
        not_applicable_reason=reason,
        evidence_summary=_summary({"reason": reason}),
    )


def _summary(values: Mapping[str, object]) -> str:
    return json.dumps(
        dict(values),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


__all__ = (
    "evaluate_cumulative_nonnegative",
    "evaluate_play_count_coverage",
    "evaluate_revision_chain",
    "evaluate_snapshot_freshness",
    "production_evaluator_registry",
)
