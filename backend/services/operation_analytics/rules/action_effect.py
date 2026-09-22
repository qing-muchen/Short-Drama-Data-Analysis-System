"""Deterministic before/after metric rules for completed actions."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from services.operation_analytics.contracts import (
    ACTION_EFFECT_RULE_VERSION,
    NON_CAUSAL_DISCLAIMER,
    AnalysisAvailability,
    AnalysisWindow,
    AvailabilityReason,
    AvailabilityStatus,
    DailyCumulativePoint,
    MetricChange,
    MetricDirection,
    OperationEffectivenessInput,
    OperationEffectivenessResult,
    OperationMetricType,
)


@dataclass(frozen=True, slots=True)
class WindowTotals:
    play_increment: int
    interaction_increment: int | None


class WindowInputError(ValueError):
    """Stable internal error carrying an Availability reason."""

    def __init__(self, reason: AvailabilityReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


def _direction(change: Decimal | int) -> MetricDirection:
    if change > 0:
        return MetricDirection.INCREASED
    if change < 0:
        return MetricDirection.DECREASED
    return MetricDirection.UNCHANGED


def _relative_change(
    before: Decimal | int,
    absolute_change: Decimal | int,
) -> Decimal | None:
    if before == 0:
        return None
    return Decimal(absolute_change) / Decimal(before)


def calculate_window_totals(
    points: tuple[DailyCumulativePoint, ...],
    window: AnalysisWindow,
    *,
    incomplete_reason: AvailabilityReason,
    required_platform_id: int | None = None,
) -> WindowTotals:
    """Convert cumulative points into totals for one inclusive day window."""

    if window.day_count <= 0:
        raise WindowInputError(incomplete_reason)

    grouped: dict[int, list[DailyCumulativePoint]] = defaultdict(list)
    for point in points:
        if required_platform_id is not None and point.platform_id != required_platform_id:
            raise WindowInputError(AvailabilityReason.INCOMPARABLE_SCOPE)
        grouped[point.platform_id].append(point)
    if not grouped:
        raise WindowInputError(incomplete_reason)

    expected_dates = tuple(
        window.start_date - timedelta(days=1) + timedelta(days=index)
        for index in range(window.day_count + 1)
    )
    play_total = 0
    interaction_total = 0
    interaction_complete = True

    for platform_points in grouped.values():
        ordered = sorted(platform_points, key=lambda point: point.business_date)
        if tuple(point.business_date for point in ordered) != expected_dates:
            raise WindowInputError(incomplete_reason)
        if len({point.business_date for point in ordered}) != len(ordered):
            raise WindowInputError(incomplete_reason)

        for previous, current in zip(ordered, ordered[1:]):
            play_delta = current.play_count - previous.play_count
            if play_delta < 0:
                raise WindowInputError(
                    AvailabilityReason.INVALID_CUMULATIVE_SEQUENCE
                )
            play_total += play_delta

            interaction_values = (
                previous.like_count,
                previous.comment_count,
                previous.favorite_count,
                previous.share_count,
                current.like_count,
                current.comment_count,
                current.favorite_count,
                current.share_count,
            )
            if any(value is None for value in interaction_values):
                interaction_complete = False
                continue

            previous_interactions = sum(
                value
                for value in (
                    previous.like_count,
                    previous.comment_count,
                    previous.favorite_count,
                    previous.share_count,
                )
                if value is not None
            )
            current_interactions = sum(
                value
                for value in (
                    current.like_count,
                    current.comment_count,
                    current.favorite_count,
                    current.share_count,
                )
                if value is not None
            )
            interaction_delta = current_interactions - previous_interactions
            if interaction_delta < 0:
                raise WindowInputError(
                    AvailabilityReason.INVALID_CUMULATIVE_SEQUENCE
                )
            interaction_total += interaction_delta

    return WindowTotals(
        play_increment=play_total,
        interaction_increment=(interaction_total if interaction_complete else None),
    )


class ActionEffectCalculator:
    """Calculate observable metric movement without a causal conclusion."""

    def calculate(
        self,
        input_data: OperationEffectivenessInput,
    ) -> OperationEffectivenessResult:
        if input_data.availability.status not in {
            AvailabilityStatus.AVAILABLE,
            AvailabilityStatus.PARTIAL,
        }:
            return self._result(input_data, (), input_data.availability)

        if input_data.before_window.day_count != 7:
            return self._unavailable(
                input_data,
                AvailabilityReason.INCOMPLETE_BEFORE_WINDOW,
            )
        anchor_date = input_data.anchor_time.date()
        if (
            input_data.before_window.start_date != anchor_date - timedelta(days=7)
            or input_data.before_window.end_date != anchor_date - timedelta(days=1)
        ):
            return self._unavailable(
                input_data,
                AvailabilityReason.INCOMPLETE_BEFORE_WINDOW,
            )
        if input_data.after_window.day_count != 7:
            return self._unavailable(
                input_data,
                AvailabilityReason.INCOMPLETE_AFTER_WINDOW,
            )
        if (
            input_data.after_window.start_date != anchor_date + timedelta(days=1)
            or input_data.after_window.end_date != anchor_date + timedelta(days=7)
        ):
            return self._unavailable(
                input_data,
                AvailabilityReason.INCOMPLETE_AFTER_WINDOW,
            )

        try:
            before = calculate_window_totals(
                input_data.before_points,
                input_data.before_window,
                incomplete_reason=AvailabilityReason.INCOMPLETE_BEFORE_WINDOW,
            )
            after = calculate_window_totals(
                input_data.after_points,
                input_data.after_window,
                incomplete_reason=AvailabilityReason.INCOMPLETE_AFTER_WINDOW,
            )
        except WindowInputError as exc:
            return self._unavailable(input_data, exc.reason)

        before_platforms = {point.platform_id for point in input_data.before_points}
        after_platforms = {point.platform_id for point in input_data.after_points}
        if before_platforms != after_platforms:
            return self._unavailable(
                input_data,
                AvailabilityReason.INCOMPARABLE_SCOPE,
            )

        metric_changes = [self._play_change(before, after)]
        metric_changes.append(self._engagement_change(before, after))
        metric_changes.append(self._growth_change(before, after))
        metric_changes.append(self._anomaly_change(input_data))

        reasons = list(input_data.availability.reasons)
        if input_data.overlapping_action_ids:
            reasons.append(AvailabilityReason.OVERLAPPING_ACTIONS)
        if len(set(input_data.anomaly_algorithm_versions)) > 1:
            reasons.append(AvailabilityReason.MIXED_SOURCE_VERSIONS)
        if any(
            metric.availability.status is not AvailabilityStatus.AVAILABLE
            for metric in metric_changes
        ):
            reasons.extend(
                reason
                for metric in metric_changes
                for reason in metric.availability.reasons
            )

        reasons = self._ordered_reasons(reasons)
        availability = (
            AnalysisAvailability(AvailabilityStatus.PARTIAL, reasons)
            if reasons
            else AnalysisAvailability(AvailabilityStatus.AVAILABLE)
        )
        return self._result(input_data, tuple(metric_changes), availability)

    @staticmethod
    def _play_change(before: WindowTotals, after: WindowTotals) -> MetricChange:
        absolute = after.play_increment - before.play_increment
        relative = _relative_change(before.play_increment, absolute)
        reasons = (
            (AvailabilityReason.ZERO_BASELINE,)
            if relative is None
            else ()
        )
        availability = (
            AnalysisAvailability(AvailabilityStatus.PARTIAL, reasons)
            if reasons
            else AnalysisAvailability(AvailabilityStatus.AVAILABLE)
        )
        return MetricChange(
            metric_type=OperationMetricType.PLAY_COUNT,
            before_value=before.play_increment,
            after_value=after.play_increment,
            absolute_change=absolute,
            relative_change=relative,
            direction=_direction(absolute),
            unit="count",
            availability=availability,
        )

    @staticmethod
    def _engagement_change(
        before: WindowTotals,
        after: WindowTotals,
    ) -> MetricChange:
        if (
            before.interaction_increment is None
            or after.interaction_increment is None
        ):
            return MetricChange(
                metric_type=OperationMetricType.ENGAGEMENT_RATE,
                before_value=None,
                after_value=None,
                absolute_change=None,
                relative_change=None,
                direction=MetricDirection.UNAVAILABLE,
                unit="ratio",
                availability=AnalysisAvailability(
                    AvailabilityStatus.INSUFFICIENT,
                    (AvailabilityReason.MISSING_METRIC,),
                ),
            )
        if before.play_increment == 0 or after.play_increment == 0:
            return MetricChange(
                metric_type=OperationMetricType.ENGAGEMENT_RATE,
                before_value=None,
                after_value=None,
                absolute_change=None,
                relative_change=None,
                direction=MetricDirection.UNAVAILABLE,
                unit="ratio",
                availability=AnalysisAvailability(
                    AvailabilityStatus.INSUFFICIENT,
                    (AvailabilityReason.ZERO_BASELINE,),
                ),
            )

        before_rate = Decimal(before.interaction_increment) / Decimal(
            before.play_increment
        )
        after_rate = Decimal(after.interaction_increment) / Decimal(
            after.play_increment
        )
        absolute = after_rate - before_rate
        return MetricChange(
            metric_type=OperationMetricType.ENGAGEMENT_RATE,
            before_value=before_rate,
            after_value=after_rate,
            absolute_change=absolute,
            relative_change=None,
            direction=_direction(absolute),
            unit="ratio",
            availability=AnalysisAvailability(AvailabilityStatus.AVAILABLE),
        )

    @staticmethod
    def _growth_change(before: WindowTotals, after: WindowTotals) -> MetricChange:
        before_average = Decimal(before.play_increment) / Decimal(7)
        after_average = Decimal(after.play_increment) / Decimal(7)
        absolute = after_average - before_average
        relative = _relative_change(before_average, absolute)
        reasons = (
            (AvailabilityReason.ZERO_BASELINE,)
            if relative is None
            else ()
        )
        availability = (
            AnalysisAvailability(AvailabilityStatus.PARTIAL, reasons)
            if reasons
            else AnalysisAvailability(AvailabilityStatus.AVAILABLE)
        )
        return MetricChange(
            metric_type=OperationMetricType.GROWTH_RATE,
            before_value=before_average,
            after_value=after_average,
            absolute_change=absolute,
            relative_change=relative,
            direction=_direction(absolute),
            unit="count_per_day",
            availability=availability,
        )

    @staticmethod
    def _anomaly_change(input_data: OperationEffectivenessInput) -> MetricChange:
        before = len(input_data.before_anomaly_ids)
        after = len(input_data.after_anomaly_ids)
        absolute = after - before
        relative = _relative_change(before, absolute)
        reasons: tuple[AvailabilityReason, ...] = ()
        if len(set(input_data.anomaly_algorithm_versions)) > 1:
            reasons = (AvailabilityReason.MIXED_SOURCE_VERSIONS,)
        availability = (
            AnalysisAvailability(AvailabilityStatus.PARTIAL, reasons)
            if reasons
            else AnalysisAvailability(AvailabilityStatus.AVAILABLE)
        )
        return MetricChange(
            metric_type=OperationMetricType.ANOMALY_COUNT,
            before_value=before,
            after_value=after,
            absolute_change=absolute,
            relative_change=relative,
            direction=_direction(absolute),
            unit="count",
            availability=availability,
        )

    @staticmethod
    def _ordered_reasons(
        reasons: list[AvailabilityReason],
    ) -> tuple[AvailabilityReason, ...]:
        included = set(reasons)
        return tuple(reason for reason in AvailabilityReason if reason in included)

    def _unavailable(
        self,
        input_data: OperationEffectivenessInput,
        reason: AvailabilityReason,
    ) -> OperationEffectivenessResult:
        status = (
            AvailabilityStatus.INSUFFICIENT
            if reason
            in {
                AvailabilityReason.INSUFFICIENT_HISTORY,
                AvailabilityReason.INCOMPLETE_BEFORE_WINDOW,
                AvailabilityReason.INCOMPLETE_AFTER_WINDOW,
                AvailabilityReason.MISSING_METRIC,
                AvailabilityReason.NOT_COMPLETED,
            }
            else AvailabilityStatus.NOT_AVAILABLE
        )
        return self._result(
            input_data,
            (),
            AnalysisAvailability(status, (reason,)),
        )

    @staticmethod
    def _result(
        input_data: OperationEffectivenessInput,
        metrics: tuple[MetricChange, ...],
        availability: AnalysisAvailability,
    ) -> OperationEffectivenessResult:
        return OperationEffectivenessResult(
            action_id=input_data.action_id,
            drama_id=input_data.drama_id,
            before_window=input_data.before_window,
            after_window=input_data.after_window,
            metric_changes=metrics,
            availability=availability,
            anchor_time=input_data.anchor_time,
            overlapping_action_ids=input_data.overlapping_action_ids,
            action_effect_rule_version=ACTION_EFFECT_RULE_VERSION,
            disclaimer=NON_CAUSAL_DISCLAIMER,
        )


__all__ = ["ActionEffectCalculator", "WindowInputError", "WindowTotals", "calculate_window_totals"]
