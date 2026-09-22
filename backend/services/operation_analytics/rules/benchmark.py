"""Deterministic same-platform benchmark statistics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from statistics import median

from services.operation_analytics.contracts import (
    BENCHMARK_VERSION,
    LIFECYCLE_RULE_VERSION,
    AnalysisAvailability,
    AvailabilityReason,
    AvailabilityStatus,
    BenchmarkInput,
    BenchmarkMemberInput,
    BenchmarkMemberResult,
    BenchmarkMetric,
    BenchmarkMetricType,
    BenchmarkResult,
)
from services.operation_analytics.rules.action_effect import (
    WindowInputError,
    calculate_window_totals,
)


@dataclass(frozen=True, slots=True)
class _MemberValues:
    member: BenchmarkMemberInput
    play_total: Decimal | None
    mean_daily: Decimal | None
    engagement_rate: Decimal | None
    anomaly_frequency: Decimal | None
    availability: AnalysisAvailability


class BenchmarkCalculator:
    """Compare a bounded explicit group without rankings or recommendations."""

    def compare(self, input_data: BenchmarkInput) -> BenchmarkResult:
        if (
            input_data.window.day_count != 30
            or input_data.window.end_date
            != input_data.analysis_as_of.date() - timedelta(days=1)
        ):
            return self._result(
                input_data,
                (),
                AnalysisAvailability(
                    AvailabilityStatus.NOT_AVAILABLE,
                    (AvailabilityReason.INCOMPARABLE_SCOPE,),
                ),
            )

        members_by_id = {member.drama_id: member for member in input_data.members}
        values = tuple(
            self._member_values(
                members_by_id.get(drama_id),
                drama_id,
                input_data,
            )
            for drama_id in input_data.comparison_scope.drama_ids
        )
        comparable_count = sum(
            value.play_total is not None
            and value.availability.status
            in {AvailabilityStatus.AVAILABLE, AvailabilityStatus.PARTIAL}
            for value in values
        )
        if comparable_count < 2:
            members = tuple(self._member_result(value, values) for value in values)
            return self._result(
                input_data,
                members,
                AnalysisAvailability(
                    AvailabilityStatus.INSUFFICIENT,
                    (AvailabilityReason.INCOMPARABLE_SCOPE,),
                ),
            )

        members = tuple(self._member_result(value, values) for value in values)
        all_available = all(
            member.availability.status is AvailabilityStatus.AVAILABLE
            for member in members
        )
        if all_available:
            availability = AnalysisAvailability(AvailabilityStatus.AVAILABLE)
        else:
            reasons = self._ordered_reasons(
                reason
                for member in members
                for reason in member.availability.reasons
            )
            availability = AnalysisAvailability(
                AvailabilityStatus.PARTIAL,
                reasons or (AvailabilityReason.MISSING_METRIC,),
            )
        return self._result(input_data, members, availability)

    @staticmethod
    def _member_values(
        member: BenchmarkMemberInput | None,
        drama_id: int,
        input_data: BenchmarkInput,
    ) -> _MemberValues:
        if member is None:
            return _MemberValues(
                member=BenchmarkMemberInput(
                    drama_id=drama_id,
                    points=(),
                    availability=AnalysisAvailability(
                        AvailabilityStatus.INSUFFICIENT,
                        (AvailabilityReason.INSUFFICIENT_HISTORY,),
                    ),
                ),
                play_total=None,
                mean_daily=None,
                engagement_rate=None,
                anomaly_frequency=None,
                availability=AnalysisAvailability(
                    AvailabilityStatus.INSUFFICIENT,
                    (AvailabilityReason.INSUFFICIENT_HISTORY,),
                ),
            )
        if member.availability.status not in {
            AvailabilityStatus.AVAILABLE,
            AvailabilityStatus.PARTIAL,
        }:
            return _MemberValues(member, None, None, None, None, member.availability)

        try:
            totals = calculate_window_totals(
                member.points,
                input_data.window,
                incomplete_reason=AvailabilityReason.INSUFFICIENT_HISTORY,
                required_platform_id=input_data.comparison_scope.platform_id,
            )
        except WindowInputError as exc:
            status = (
                AvailabilityStatus.INSUFFICIENT
                if exc.reason is AvailabilityReason.INSUFFICIENT_HISTORY
                else AvailabilityStatus.NOT_AVAILABLE
            )
            availability = AnalysisAvailability(status, (exc.reason,))
            return _MemberValues(member, None, None, None, None, availability)

        play_total = Decimal(totals.play_increment)
        mean_daily = play_total / Decimal(30)
        engagement_rate = (
            Decimal(totals.interaction_increment) / play_total
            if totals.interaction_increment is not None and play_total > 0
            else None
        )
        anomaly_frequency = Decimal(len(member.anomaly_ids)) / Decimal(30)

        reasons = list(member.availability.reasons)
        if totals.interaction_increment is None:
            reasons.append(AvailabilityReason.MISSING_METRIC)
        elif play_total == 0:
            reasons.append(AvailabilityReason.ZERO_BASELINE)
        if len(set(member.anomaly_algorithm_versions)) > 1:
            reasons.append(AvailabilityReason.MIXED_SOURCE_VERSIONS)
        lifecycle = member.lifecycle_result
        if lifecycle is None:
            reasons.append(AvailabilityReason.NOT_CALCULATED)
        elif lifecycle.availability.status is not AvailabilityStatus.AVAILABLE:
            reasons.extend(lifecycle.availability.reasons)
        ordered = BenchmarkCalculator._ordered_reasons(reasons)
        availability = (
            AnalysisAvailability(AvailabilityStatus.PARTIAL, ordered)
            if ordered
            else AnalysisAvailability(AvailabilityStatus.AVAILABLE)
        )
        return _MemberValues(
            member,
            play_total,
            mean_daily,
            engagement_rate,
            anomaly_frequency,
            availability,
        )

    @classmethod
    def _member_result(
        cls,
        values: _MemberValues,
        group: tuple[_MemberValues, ...],
    ) -> BenchmarkMemberResult:
        metrics = (
            cls._metric(
                BenchmarkMetricType.PLAY_INCREMENT_TOTAL,
                values.play_total,
                cls._median(group, "play_total"),
                "count",
            ),
            cls._metric(
                BenchmarkMetricType.MEAN_DAILY_PLAY_INCREMENT,
                values.mean_daily,
                cls._median(group, "mean_daily"),
                "count_per_day",
            ),
            cls._metric(
                BenchmarkMetricType.ENGAGEMENT_RATE,
                values.engagement_rate,
                cls._median(group, "engagement_rate"),
                "ratio",
            ),
            cls._metric(
                BenchmarkMetricType.ANOMALY_FREQUENCY,
                values.anomaly_frequency,
                cls._median(group, "anomaly_frequency"),
                "count_per_day",
            ),
            cls._lifecycle_metric(values),
        )
        return BenchmarkMemberResult(
            drama_id=values.member.drama_id,
            metrics=metrics,
            availability=values.availability,
        )

    @staticmethod
    def _metric(
        metric_type: BenchmarkMetricType,
        value: Decimal | None,
        group_median: Decimal | None,
        unit: str,
    ) -> BenchmarkMetric:
        if value is None:
            availability = AnalysisAvailability(
                AvailabilityStatus.INSUFFICIENT,
                (AvailabilityReason.MISSING_METRIC,),
            )
        else:
            availability = AnalysisAvailability(AvailabilityStatus.AVAILABLE)
        return BenchmarkMetric(
            metric_type=metric_type,
            value=value,
            group_median=group_median,
            unit=unit,
            availability=availability,
        )

    @staticmethod
    def _lifecycle_metric(values: _MemberValues) -> BenchmarkMetric:
        lifecycle = values.member.lifecycle_result
        if lifecycle is None or lifecycle.lifecycle_stage is None:
            return BenchmarkMetric(
                metric_type=BenchmarkMetricType.LIFECYCLE_STATE,
                value=None,
                group_median=None,
                unit="stage",
                availability=AnalysisAvailability(
                    AvailabilityStatus.INSUFFICIENT,
                    (AvailabilityReason.NOT_CALCULATED,),
                ),
            )
        return BenchmarkMetric(
            metric_type=BenchmarkMetricType.LIFECYCLE_STATE,
            value=lifecycle.lifecycle_stage.value,
            group_median=None,
            unit="stage",
            availability=lifecycle.availability,
        )

    @staticmethod
    def _median(
        group: tuple[_MemberValues, ...],
        attribute: str,
    ) -> Decimal | None:
        values = [
            value
            for member in group
            if (value := getattr(member, attribute)) is not None
            and member.availability.status
            in {AvailabilityStatus.AVAILABLE, AvailabilityStatus.PARTIAL}
        ]
        return median(values) if len(values) >= 2 else None

    @staticmethod
    def _ordered_reasons(
        reasons,
    ) -> tuple[AvailabilityReason, ...]:
        included = set(reasons)
        return tuple(reason for reason in AvailabilityReason if reason in included)

    @staticmethod
    def _result(
        input_data: BenchmarkInput,
        members: tuple[BenchmarkMemberResult, ...],
        availability: AnalysisAvailability,
    ) -> BenchmarkResult:
        return BenchmarkResult(
            target_drama_id=None,
            comparison_scope=input_data.comparison_scope,
            window=input_data.window,
            metrics=members,
            availability=availability,
            benchmark_version=BENCHMARK_VERSION,
            lifecycle_rule_version=LIFECYCLE_RULE_VERSION,
            analysis_revision=None,
            analysis_as_of=input_data.analysis_as_of,
        )


__all__ = ["BenchmarkCalculator"]
