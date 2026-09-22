"""Deterministic lifecycle classification rules."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from services.operation_analytics.contracts import (
    LIFECYCLE_RULE_VERSION,
    AnalysisAvailability,
    AnalysisWindow,
    AvailabilityReason,
    AvailabilityStatus,
    LifecycleEvidence,
    LifecycleInput,
    LifecycleResult,
    LifecycleStage,
)


class LifecycleClassifier:
    """Classify a point-in-time lifecycle state using fixed V1 rules."""

    def classify(self, input_data: LifecycleInput) -> LifecycleResult:
        if input_data.drama_status == "INACTIVE":
            return self._result(input_data, LifecycleStage.ARCHIVED)

        release_time = input_data.release_time
        if release_time is None or release_time > input_data.analysis_as_of:
            return self._unavailable(
                input_data,
                AvailabilityStatus.NOT_AVAILABLE,
                AvailabilityReason.NOT_AVAILABLE,
            )

        days_since_release = (
            input_data.analysis_as_of.date() - release_time.date()
        ).days
        if 0 <= days_since_release <= 14:
            return self._result(input_data, LifecycleStage.LAUNCH)

        increments = self._daily_play_increments(input_data)
        if increments is None:
            return self._unavailable(
                input_data,
                AvailabilityStatus.INSUFFICIENT,
                AvailabilityReason.INSUFFICIENT_HISTORY,
            )
        if increments is False:
            return self._unavailable(
                input_data,
                AvailabilityStatus.NOT_AVAILABLE,
                AvailabilityReason.INVALID_CUMULATIVE_SEQUENCE,
            )

        previous = increments[:7]
        current = increments[7:]
        previous_average = sum(previous, Decimal(0)) / Decimal(7)
        current_average = sum(current, Decimal(0)) / Decimal(7)

        if previous_average == 0:
            rate = None
            stage = (
                LifecycleStage.GROWTH
                if current_average > 0
                else LifecycleStage.STABLE
            )
        else:
            rate = (current_average - previous_average) / previous_average
            if rate >= Decimal("0.10"):
                stage = LifecycleStage.GROWTH
            elif rate <= Decimal("-0.10"):
                stage = LifecycleStage.DECLINE
            else:
                stage = LifecycleStage.STABLE

        dates = sorted({point.business_date for point in input_data.points})
        evidence = LifecycleEvidence(
            previous_window=AnalysisWindow(dates[1], dates[7], 7),
            current_window=AnalysisWindow(dates[8], dates[14], 7),
            previous_average=previous_average,
            current_average=current_average,
            window_change_rate=rate,
        )
        return self._result(input_data, stage, evidence)

    @staticmethod
    def _daily_play_increments(
        input_data: LifecycleInput,
    ) -> tuple[Decimal, ...] | None | bool:
        grouped: dict[int, list] = defaultdict(list)
        for point in input_data.points:
            grouped[point.platform_id].append(point)
        if not grouped:
            return None

        expected_end = input_data.analysis_as_of.date() - timedelta(days=1)
        expected_dates = tuple(
            expected_end - timedelta(days=14 - index) for index in range(15)
        )
        aggregated = [Decimal(0) for _ in expected_dates]

        for points in grouped.values():
            ordered = sorted(points, key=lambda point: point.business_date)
            if tuple(point.business_date for point in ordered) != expected_dates:
                return None
            for index, point in enumerate(ordered):
                aggregated[index] += Decimal(point.play_count)

        increments = tuple(
            current - previous
            for previous, current in zip(aggregated, aggregated[1:])
        )
        if any(increment < 0 for increment in increments):
            return False
        return increments

    @staticmethod
    def _result(
        input_data: LifecycleInput,
        stage: LifecycleStage,
        evidence: LifecycleEvidence | None = None,
    ) -> LifecycleResult:
        return LifecycleResult(
            drama_id=input_data.drama_id,
            lifecycle_stage=stage,
            rule_version=LIFECYCLE_RULE_VERSION,
            evaluated_as_of=input_data.analysis_as_of,
            availability=AnalysisAvailability(AvailabilityStatus.AVAILABLE),
            evidence=evidence,
        )

    @staticmethod
    def _unavailable(
        input_data: LifecycleInput,
        status: AvailabilityStatus,
        reason: AvailabilityReason,
    ) -> LifecycleResult:
        return LifecycleResult(
            drama_id=input_data.drama_id,
            lifecycle_stage=None,
            rule_version=LIFECYCLE_RULE_VERSION,
            evaluated_as_of=input_data.analysis_as_of,
            availability=AnalysisAvailability(status, (reason,)),
        )


__all__ = ["LifecycleClassifier"]
