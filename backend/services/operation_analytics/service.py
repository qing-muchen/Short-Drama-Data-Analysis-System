"""Read-only orchestration service for Phase 8 operation analytics."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import logging
from typing import Protocol, Sequence
from zoneinfo import ZoneInfo

from services.exceptions import ValidationException
from services.operation_analytics.contracts import (
    ACTION_EFFECT_RULE_VERSION,
    BENCHMARK_VERSION,
    LIFECYCLE_RULE_VERSION,
    AnalysisAvailability,
    AnalysisRevisionInput,
    AnalysisWindow,
    AvailabilityReason,
    AvailabilityStatus,
    BenchmarkInput,
    BenchmarkMemberInput,
    BenchmarkResult,
    ComparisonScope,
    LifecycleInput,
    LifecycleResult,
    OperationEffectivenessInput,
    OperationEffectivenessResult,
)
from services.operation_analytics.providers import (
    BenchmarkProvider,
    LifecycleInputProvider,
    OperationEffectivenessInputPage,
    OperationEffectivenessProvider,
)
from services.operation_analytics.rules import (
    ActionEffectCalculator,
    AnalysisRevisionBuilder,
    BenchmarkCalculator,
    LifecycleClassifier,
)


LOGGER = logging.getLogger(__name__)
BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")


class Clock(Protocol):
    """Injectable request clock used only at the Service entry point."""

    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class OperationEffectivenessResultPage:
    page: int
    page_size: int
    total: int
    items: tuple[OperationEffectivenessResult, ...]
    availability: AnalysisAvailability
    analysis_as_of: datetime


class OperationAnalyticsService:
    """Coordinate providers and deterministic rules without data access."""

    def __init__(
        self,
        operation_effectiveness_provider: OperationEffectivenessProvider,
        lifecycle_input_provider: LifecycleInputProvider,
        benchmark_provider: BenchmarkProvider,
        action_effect_calculator: ActionEffectCalculator,
        lifecycle_classifier: LifecycleClassifier,
        benchmark_calculator: BenchmarkCalculator,
        revision_builder: AnalysisRevisionBuilder,
        clock: Clock,
    ) -> None:
        self.operation_effectiveness_provider = operation_effectiveness_provider
        self.lifecycle_input_provider = lifecycle_input_provider
        self.benchmark_provider = benchmark_provider
        self.action_effect_calculator = action_effect_calculator
        self.lifecycle_classifier = lifecycle_classifier
        self.benchmark_calculator = benchmark_calculator
        self.revision_builder = revision_builder
        self.clock = clock

    def get_operation_effectiveness(
        self,
        *,
        action_id: int | None = None,
        drama_id: int | None = None,
        analysis_as_of: datetime | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> OperationEffectivenessResultPage:
        self._validate_optional_id(action_id, "action_id")
        self._validate_optional_id(drama_id, "drama_id")
        self._validate_page(page, page_size)
        frozen_as_of = self._freeze_analysis_as_of(analysis_as_of)

        try:
            input_page = self.operation_effectiveness_provider.get_inputs(
                action_id=action_id,
                drama_id=drama_id,
                analysis_as_of=frozen_as_of,
                page=page,
                page_size=page_size,
            )
            if not isinstance(input_page, OperationEffectivenessInputPage):
                raise TypeError("Operation effectiveness provider returned invalid data")
            self._validate_action_input_page(
                input_page,
                action_id=action_id,
                drama_id=drama_id,
                page=page,
                page_size=page_size,
            )
        except Exception:
            LOGGER.exception("Operation effectiveness provider failed")
            return OperationEffectivenessResultPage(
                page=page,
                page_size=page_size,
                total=0,
                items=(),
                availability=self._not_available(),
                analysis_as_of=frozen_as_of,
            )

        results = tuple(
            self._calculate_action_effect(input_data, frozen_as_of)
            for input_data in input_page.items
        )
        return OperationEffectivenessResultPage(
            page=input_page.page,
            page_size=input_page.page_size,
            total=input_page.total,
            items=results,
            availability=self._aggregate_availability(
                tuple(result.availability for result in results)
            ),
            analysis_as_of=frozen_as_of,
        )

    def get_lifecycle(
        self,
        *,
        drama_id: int,
        analysis_as_of: datetime | None = None,
    ) -> LifecycleResult:
        self._validate_id(drama_id, "drama_id")
        frozen_as_of = self._freeze_analysis_as_of(analysis_as_of)
        try:
            input_data = self.lifecycle_input_provider.get_input(
                drama_id=drama_id,
                analysis_as_of=frozen_as_of,
            )
        except Exception:
            LOGGER.exception("Lifecycle provider failed for drama %s", drama_id)
            return self._unavailable_lifecycle(drama_id, frozen_as_of)
        if input_data is None:
            return self._unavailable_lifecycle(drama_id, frozen_as_of)
        if (
            not isinstance(input_data, LifecycleInput)
            or input_data.drama_id != drama_id
            or input_data.analysis_as_of != frozen_as_of
        ):
            LOGGER.error("Lifecycle provider returned a mismatched input context")
            return self._unavailable_lifecycle(drama_id, frozen_as_of)

        try:
            result = self.lifecycle_classifier.classify(input_data)
            if not isinstance(result, LifecycleResult):
                raise TypeError("Lifecycle classifier returned invalid data")
        except Exception:
            LOGGER.exception("Lifecycle classification failed for drama %s", drama_id)
            return self._unavailable_lifecycle(
                drama_id,
                frozen_as_of,
                input_data=input_data,
            )
        revision = self._build_lifecycle_revision(input_data, frozen_as_of)
        return replace(
            result,
            evaluated_as_of=frozen_as_of,
            analysis_revision=revision,
        )

    def get_benchmark(
        self,
        *,
        drama_ids: Sequence[int],
        platform_id: int,
        analysis_as_of: datetime | None = None,
    ) -> BenchmarkResult:
        normalized_ids = self._validate_benchmark_ids(drama_ids)
        self._validate_id(platform_id, "platform_id")
        frozen_as_of = self._freeze_analysis_as_of(analysis_as_of)
        try:
            input_data = self.benchmark_provider.get_input(
                drama_ids=normalized_ids,
                platform_id=platform_id,
                analysis_as_of=frozen_as_of,
            )
            if not isinstance(input_data, BenchmarkInput):
                raise TypeError("Benchmark provider returned invalid data")
            if (
                input_data.comparison_scope.drama_ids != normalized_ids
                or input_data.comparison_scope.platform_id != platform_id
                or input_data.analysis_as_of != frozen_as_of
            ):
                raise TypeError("Benchmark provider returned a mismatched scope")
        except Exception:
            LOGGER.exception("Benchmark provider failed")
            return self._unavailable_benchmark(
                normalized_ids,
                platform_id,
                frozen_as_of,
            )

        enriched = replace(
            input_data,
            members=tuple(
                self._enrich_benchmark_member(member, frozen_as_of)
                for member in input_data.members
            ),
        )
        try:
            result = self.benchmark_calculator.compare(enriched)
            if not isinstance(result, BenchmarkResult):
                raise TypeError("Benchmark calculator returned invalid data")
        except Exception:
            LOGGER.exception("Benchmark calculation failed")
            return self._unavailable_benchmark(
                normalized_ids,
                platform_id,
                frozen_as_of,
                input_data=enriched,
            )
        revision = self._build_benchmark_revision(enriched, frozen_as_of)
        return replace(
            result,
            analysis_as_of=frozen_as_of,
            analysis_revision=revision,
        )

    def _calculate_action_effect(
        self,
        input_data: OperationEffectivenessInput,
        analysis_as_of: datetime,
    ) -> OperationEffectivenessResult:
        try:
            result = self.action_effect_calculator.calculate(input_data)
            if not isinstance(result, OperationEffectivenessResult):
                raise TypeError("Action effect calculator returned invalid data")
        except Exception:
            LOGGER.exception(
                "Action effect calculation failed for action %s",
                input_data.action_id,
            )
            result = OperationEffectivenessResult(
                action_id=input_data.action_id,
                drama_id=input_data.drama_id,
                before_window=input_data.before_window,
                after_window=input_data.after_window,
                metric_changes=(),
                availability=self._not_available(),
                anchor_time=input_data.anchor_time,
                overlapping_action_ids=input_data.overlapping_action_ids,
            )
        revision = self._build_action_revision(input_data, analysis_as_of)
        return replace(
            result,
            analysis_revision=revision,
            analysis_as_of=analysis_as_of,
        )

    def _enrich_benchmark_member(
        self,
        member: BenchmarkMemberInput,
        analysis_as_of: datetime,
    ) -> BenchmarkMemberInput:
        try:
            lifecycle_input = self.lifecycle_input_provider.get_input(
                drama_id=member.drama_id,
                analysis_as_of=analysis_as_of,
            )
            lifecycle = (
                self.lifecycle_classifier.classify(lifecycle_input)
                if lifecycle_input is not None
                else None
            )
            if lifecycle is not None and not isinstance(lifecycle, LifecycleResult):
                raise TypeError("Lifecycle classifier returned invalid data")
            return replace(member, lifecycle_result=lifecycle)
        except Exception:
            LOGGER.exception(
                "Lifecycle enrichment failed for benchmark drama %s",
                member.drama_id,
            )
            return replace(
                member,
                lifecycle_result=None,
                availability=self._merge_not_available(member.availability),
            )

    def _build_action_revision(
        self,
        input_data: OperationEffectivenessInput,
        analysis_as_of: datetime,
    ) -> str:
        anomaly_ids = tuple(
            sorted({*input_data.before_anomaly_ids, *input_data.after_anomaly_ids})
        )
        versions = "|".join(sorted(set(input_data.anomaly_algorithm_versions)))
        return self.revision_builder.build(
            AnalysisRevisionInput(
                analysis_type="OPERATION_EFFECTIVENESS",
                entity_ids=(input_data.action_id, input_data.drama_id),
                parameters=(
                    ("before_window", self._window_value(input_data.before_window)),
                    ("after_window", self._window_value(input_data.after_window)),
                    ("anomaly_versions", versions),
                ),
                analysis_as_of=analysis_as_of,
                snapshot_revision_ids=self._snapshot_ids(
                    (*input_data.before_points, *input_data.after_points)
                ),
                source_result_versions=tuple(
                    (anomaly_id, versions) for anomaly_id in anomaly_ids if versions
                ),
                rule_versions=(ACTION_EFFECT_RULE_VERSION,),
            )
        )

    def _build_lifecycle_revision(self, input_data, analysis_as_of: datetime) -> str:
        return self.revision_builder.build(
            AnalysisRevisionInput(
                analysis_type="LIFECYCLE",
                entity_ids=(input_data.drama_id,),
                parameters=(
                    ("drama_status", input_data.drama_status),
                    (
                        "release_time",
                        input_data.release_time.isoformat()
                        if input_data.release_time is not None
                        else "",
                    ),
                ),
                analysis_as_of=analysis_as_of,
                snapshot_revision_ids=self._snapshot_ids(input_data.points),
                rule_versions=(LIFECYCLE_RULE_VERSION,),
            )
        )

    def _build_benchmark_revision(
        self,
        input_data: BenchmarkInput,
        analysis_as_of: datetime,
    ) -> str:
        points = tuple(point for member in input_data.members for point in member.points)
        versions = tuple(
            sorted(
                {
                    version
                    for member in input_data.members
                    for version in member.anomaly_algorithm_versions
                }
            )
        )
        return self.revision_builder.build(
            AnalysisRevisionInput(
                analysis_type="BENCHMARK",
                entity_ids=input_data.comparison_scope.drama_ids,
                parameters=(
                    ("platform_id", str(input_data.comparison_scope.platform_id)),
                    ("window", self._window_value(input_data.window)),
                    ("anomaly_versions", "|".join(versions)),
                ),
                analysis_as_of=analysis_as_of,
                snapshot_revision_ids=self._snapshot_ids(points),
                rule_versions=(BENCHMARK_VERSION, LIFECYCLE_RULE_VERSION),
            )
        )

    def _unavailable_lifecycle(
        self,
        drama_id: int,
        analysis_as_of: datetime,
        *,
        input_data=None,
    ) -> LifecycleResult:
        revision = self.revision_builder.build(
            AnalysisRevisionInput(
                analysis_type="LIFECYCLE",
                entity_ids=(drama_id,),
                parameters=(),
                analysis_as_of=analysis_as_of,
                snapshot_revision_ids=(
                    self._snapshot_ids(input_data.points)
                    if input_data is not None
                    else ()
                ),
                rule_versions=(LIFECYCLE_RULE_VERSION,),
            )
        )
        return LifecycleResult(
            drama_id=drama_id,
            lifecycle_stage=None,
            rule_version=LIFECYCLE_RULE_VERSION,
            evaluated_as_of=analysis_as_of,
            availability=self._not_available(),
            analysis_revision=revision,
        )

    def _unavailable_benchmark(
        self,
        drama_ids: tuple[int, ...],
        platform_id: int,
        analysis_as_of: datetime,
        *,
        input_data: BenchmarkInput | None = None,
    ) -> BenchmarkResult:
        if input_data is None:
            business_date = analysis_as_of.astimezone(BUSINESS_TIMEZONE).date()
            end_date = business_date - timedelta(days=1)
            window = AnalysisWindow(end_date - timedelta(days=29), end_date, 30)
            scope = ComparisonScope(drama_ids, platform_id)
            input_data = BenchmarkInput(scope, window, (), analysis_as_of)
        revision = self._build_benchmark_revision(input_data, analysis_as_of)
        return BenchmarkResult(
            target_drama_id=None,
            comparison_scope=input_data.comparison_scope,
            window=input_data.window,
            metrics=(),
            availability=self._not_available(),
            benchmark_version=BENCHMARK_VERSION,
            lifecycle_rule_version=LIFECYCLE_RULE_VERSION,
            analysis_revision=revision,
            analysis_as_of=analysis_as_of,
        )

    def _freeze_analysis_as_of(self, value: datetime | None) -> datetime:
        candidate = self.clock.now() if value is None else value
        if not isinstance(candidate, datetime):
            raise ValidationException("analysis_as_of must be a datetime")
        if candidate.tzinfo is None or candidate.utcoffset() is None:
            raise ValidationException("analysis_as_of must be timezone-aware")
        return candidate.astimezone(timezone.utc)

    @staticmethod
    def _validate_id(value: int, field_name: str) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValidationException(f"{field_name} must be a positive integer")

    @classmethod
    def _validate_optional_id(cls, value: int | None, field_name: str) -> None:
        if value is not None:
            cls._validate_id(value, field_name)

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if isinstance(page, bool) or not isinstance(page, int) or page < 1:
            raise ValidationException("page must be greater than or equal to 1")
        if (
            isinstance(page_size, bool)
            or not isinstance(page_size, int)
            or not 1 <= page_size <= 100
        ):
            raise ValidationException("page_size must be between 1 and 100")

    @classmethod
    def _validate_benchmark_ids(
        cls, drama_ids: Sequence[int]
    ) -> tuple[int, ...]:
        if drama_ids is None or isinstance(drama_ids, (str, bytes)):
            raise ValidationException("drama_ids must be a sequence of integers")
        try:
            normalized = tuple(dict.fromkeys(drama_ids))
        except TypeError as error:
            raise ValidationException(
                "drama_ids must be a sequence of integers"
            ) from error
        if not 2 <= len(normalized) <= 20:
            raise ValidationException("drama_ids must contain 2 to 20 unique IDs")
        for drama_id in normalized:
            cls._validate_id(drama_id, "drama_ids")
        return normalized

    @staticmethod
    def _validate_action_input_page(
        input_page: OperationEffectivenessInputPage,
        *,
        action_id: int | None,
        drama_id: int | None,
        page: int,
        page_size: int,
    ) -> None:
        if input_page.page != page or input_page.page_size != page_size:
            raise TypeError("Operation effectiveness provider changed pagination")
        if input_page.total < len(input_page.items):
            raise TypeError("Operation effectiveness provider returned invalid total")
        for item in input_page.items:
            if not isinstance(item, OperationEffectivenessInput):
                raise TypeError("Operation effectiveness provider returned invalid input")
            if action_id is not None and item.action_id != action_id:
                raise TypeError("Operation effectiveness provider changed action scope")
            if drama_id is not None and item.drama_id != drama_id:
                raise TypeError("Operation effectiveness provider changed drama scope")

    @staticmethod
    def _snapshot_ids(points) -> tuple[int, ...]:
        return tuple(sorted({point.snapshot_revision_id for point in points}))

    @staticmethod
    def _window_value(window: AnalysisWindow) -> str:
        return f"{window.start_date.isoformat()}/{window.end_date.isoformat()}"

    @staticmethod
    def _not_available() -> AnalysisAvailability:
        return AnalysisAvailability(
            AvailabilityStatus.NOT_AVAILABLE,
            (AvailabilityReason.NOT_AVAILABLE,),
        )

    @classmethod
    def _merge_not_available(
        cls, availability: AnalysisAvailability
    ) -> AnalysisAvailability:
        reasons = cls._ordered_reasons(
            (*availability.reasons, AvailabilityReason.NOT_AVAILABLE)
        )
        return AnalysisAvailability(AvailabilityStatus.NOT_AVAILABLE, reasons)

    @classmethod
    def _aggregate_availability(
        cls, values: tuple[AnalysisAvailability, ...]
    ) -> AnalysisAvailability:
        if not values or all(
            value.status is AvailabilityStatus.AVAILABLE for value in values
        ):
            return AnalysisAvailability(AvailabilityStatus.AVAILABLE)
        reasons = cls._ordered_reasons(
            reason for value in values for reason in value.reasons
        )
        statuses = {value.status for value in values}
        if statuses == {AvailabilityStatus.INSUFFICIENT}:
            status = AvailabilityStatus.INSUFFICIENT
        elif statuses == {AvailabilityStatus.NOT_AVAILABLE}:
            status = AvailabilityStatus.NOT_AVAILABLE
        else:
            status = AvailabilityStatus.PARTIAL
        return AnalysisAvailability(
            status,
            reasons or (AvailabilityReason.NOT_AVAILABLE,),
        )

    @staticmethod
    def _ordered_reasons(reasons) -> tuple[AvailabilityReason, ...]:
        included = set(reasons)
        return tuple(reason for reason in AvailabilityReason if reason in included)


__all__ = [
    "Clock",
    "OperationAnalyticsService",
    "OperationEffectivenessResultPage",
    "SystemClock",
]
