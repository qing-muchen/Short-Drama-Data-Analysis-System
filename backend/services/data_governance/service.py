"""Read-only orchestration service for Phase 9 data governance."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import logging
from typing import Iterable, Protocol

from services.data_governance.contracts import (
    COMPLETENESS_RULE_VERSION,
    CONSISTENCY_RULE_VERSION,
    FRESHNESS_RULE_VERSION,
    GOVERNANCE_RULE_SET_VERSION,
    AvailabilityReason,
    AvailabilityStatus,
    CompletenessResult,
    CompletenessRuleInput,
    ConsistencyResult,
    ConsistencyRuleInput,
    DataGovernanceResponse,
    DataQualityAvailability,
    EvidenceItem,
    FreshnessResult,
    FreshnessRuleInput,
    GovernanceScope,
    QualityIssueType,
    QualityStatus,
)
from services.data_governance.providers import (
    CompletenessProvider,
    ConsistencyProvider,
    FreshnessProvider,
)
from services.data_governance.rules import (
    CompletenessRule,
    ConsistencyRule,
    FreshnessRule,
)
from services.exceptions import ValidationException


LOGGER = logging.getLogger(__name__)


class Clock(Protocol):
    """Injectable clock read only at the public Service boundary."""

    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class DataGovernanceService:
    """Coordinate providers and rules without querying or mutating data."""

    def __init__(
        self,
        freshness_provider: FreshnessProvider,
        completeness_provider: CompletenessProvider,
        consistency_provider: ConsistencyProvider,
        freshness_rule: FreshnessRule,
        completeness_rule: CompletenessRule,
        consistency_rule: ConsistencyRule,
        clock: Clock,
    ) -> None:
        self.freshness_provider = freshness_provider
        self.completeness_provider = completeness_provider
        self.consistency_provider = consistency_provider
        self.freshness_rule = freshness_rule
        self.completeness_rule = completeness_rule
        self.consistency_rule = consistency_rule
        self.clock = clock

    def get_overview(
        self,
        *,
        analysis_as_of: datetime | None = None,
    ) -> DataGovernanceResponse:
        frozen_as_of = self._freeze_analysis_as_of(analysis_as_of)
        freshness = self._get_freshness(frozen_as_of, evidence_limit=5)
        completeness = self._get_completeness(frozen_as_of, evidence_limit=5)
        consistency = self._get_consistency(frozen_as_of, evidence_limit=5)
        availability = self._aggregate_availability(
            (
                freshness.availability,
                completeness.availability,
                consistency.availability,
            )
        )
        return DataGovernanceResponse(
            analysis_as_of=frozen_as_of,
            scope=GovernanceScope.SYSTEM,
            availability=availability,
            freshness=freshness,
            completeness=completeness,
            consistency=consistency,
            rule_set_version=GOVERNANCE_RULE_SET_VERSION,
        )

    def get_freshness(
        self,
        *,
        analysis_as_of: datetime | None = None,
    ) -> FreshnessResult:
        frozen_as_of = self._freeze_analysis_as_of(analysis_as_of)
        return self._get_freshness(frozen_as_of)

    def get_completeness(
        self,
        *,
        analysis_as_of: datetime | None = None,
    ) -> CompletenessResult:
        frozen_as_of = self._freeze_analysis_as_of(analysis_as_of)
        return self._get_completeness(frozen_as_of)

    def get_consistency(
        self,
        *,
        analysis_as_of: datetime | None = None,
    ) -> ConsistencyResult:
        frozen_as_of = self._freeze_analysis_as_of(analysis_as_of)
        return self._get_consistency(frozen_as_of)

    def _get_freshness(
        self,
        analysis_as_of: datetime,
        *,
        evidence_limit: int | None = None,
    ) -> FreshnessResult:
        try:
            inputs = self.freshness_provider.get_rule_inputs(
                analysis_as_of=analysis_as_of
            )
            if not isinstance(inputs, tuple) or any(
                not isinstance(item, FreshnessRuleInput) for item in inputs
            ):
                raise TypeError("FreshnessProvider returned invalid inputs")
            if any(item.current_timestamp != analysis_as_of for item in inputs):
                raise TypeError("FreshnessProvider changed analysis_as_of")
            if not inputs:
                inputs = (
                    FreshnessRuleInput(
                        entity_type=GovernanceScope.SYSTEM.value,
                        entity_id="freshness",
                        latest_timestamp=None,
                        current_timestamp=analysis_as_of,
                    ),
                )
            results = tuple(self.freshness_rule.evaluate(item) for item in inputs)
            if any(not isinstance(result, FreshnessResult) for result in results):
                raise TypeError("FreshnessRule returned invalid results")
            return self._aggregate_freshness(
                results,
                analysis_as_of,
                evidence_limit=evidence_limit,
            )
        except Exception as error:
            LOGGER.exception("Freshness governance evaluation failed")
            return self._unavailable_freshness(analysis_as_of, error)

    def _get_completeness(
        self,
        analysis_as_of: datetime,
        *,
        evidence_limit: int | None = None,
    ) -> CompletenessResult:
        try:
            inputs = self.completeness_provider.get_rule_inputs(
                analysis_as_of=analysis_as_of
            )
            if not isinstance(inputs, tuple) or any(
                not isinstance(item, CompletenessRuleInput) for item in inputs
            ):
                raise TypeError("CompletenessProvider returned invalid inputs")
            if not inputs:
                inputs = (
                    CompletenessRuleInput(
                        expected_fields=(),
                        available_fields=(),
                        metric_coverage=(),
                    ),
                )
            results = tuple(self.completeness_rule.evaluate(item) for item in inputs)
            if any(not isinstance(result, CompletenessResult) for result in results):
                raise TypeError("CompletenessRule returned invalid results")
            return self._aggregate_completeness(
                results,
                analysis_as_of,
                evidence_limit=evidence_limit,
            )
        except Exception as error:
            LOGGER.exception("Completeness governance evaluation failed")
            return self._unavailable_completeness(analysis_as_of, error)

    def _get_consistency(
        self,
        analysis_as_of: datetime,
        *,
        evidence_limit: int | None = None,
    ) -> ConsistencyResult:
        try:
            rule_input = self.consistency_provider.get_rule_input(
                analysis_as_of=analysis_as_of
            )
            if not isinstance(rule_input, ConsistencyRuleInput):
                raise TypeError("ConsistencyProvider returned invalid input")
            if rule_input.as_of_timestamp != analysis_as_of:
                raise TypeError("ConsistencyProvider changed analysis_as_of")
            result = self.consistency_rule.evaluate(rule_input)
            if not isinstance(result, ConsistencyResult):
                raise TypeError("ConsistencyRule returned an invalid result")
            evidence = self._limit_evidence(result.evidence, evidence_limit)
            return replace(
                result,
                issue_count=len(evidence),
                evidence=evidence,
                analysis_as_of=analysis_as_of,
            )
        except Exception as error:
            LOGGER.exception("Consistency governance evaluation failed")
            return self._unavailable_consistency(analysis_as_of, error)

    @classmethod
    def _aggregate_freshness(
        cls,
        results: tuple[FreshnessResult, ...],
        analysis_as_of: datetime,
        *,
        evidence_limit: int | None,
    ) -> FreshnessResult:
        evidence = cls._limit_evidence(
            tuple(item for result in results for item in result.evidence),
            evidence_limit,
        )
        delays = tuple(
            result.delay_seconds
            for result in results
            if result.delay_seconds is not None
        )
        return FreshnessResult(
            status=cls._aggregate_quality_status(
                tuple(result.status for result in results)
            ),
            availability=cls._aggregate_availability(
                tuple(result.availability for result in results)
            ),
            delay_seconds=max(delays) if delays else None,
            evidence=evidence,
            analysis_as_of=analysis_as_of,
            rule_version=FRESHNESS_RULE_VERSION,
            summary=f"Freshness evaluated for {len(results)} input(s).",
        )

    @classmethod
    def _aggregate_completeness(
        cls,
        results: tuple[CompletenessResult, ...],
        analysis_as_of: datetime,
        *,
        evidence_limit: int | None,
    ) -> CompletenessResult:
        evidence = cls._limit_evidence(
            tuple(item for result in results for item in result.evidence),
            evidence_limit,
        )
        ratios = tuple(
            result.coverage_ratio
            for result in results
            if result.coverage_ratio is not None
        )
        missing_items = tuple(
            dict.fromkeys(
                item
                for result in results
                for item in result.missing_items
            )
        )
        return CompletenessResult(
            status=cls._aggregate_quality_status(
                tuple(result.status for result in results)
            ),
            availability=cls._aggregate_availability(
                tuple(result.availability for result in results)
            ),
            coverage_ratio=min(ratios) if ratios else None,
            missing_items=missing_items,
            evidence=evidence,
            analysis_as_of=analysis_as_of,
            rule_version=COMPLETENESS_RULE_VERSION,
            summary=f"Completeness evaluated for {len(results)} input(s).",
        )

    def _freeze_analysis_as_of(self, value: datetime | None) -> datetime:
        candidate = self.clock.now() if value is None else value
        if not isinstance(candidate, datetime):
            raise ValidationException("analysis_as_of must be a datetime")
        if candidate.tzinfo is None or candidate.utcoffset() is None:
            raise ValidationException("analysis_as_of must be timezone-aware")
        return candidate.astimezone(timezone.utc)

    @classmethod
    def _aggregate_availability(
        cls,
        values: tuple[DataQualityAvailability, ...],
    ) -> DataQualityAvailability:
        if not values or all(
            value.status is AvailabilityStatus.AVAILABLE for value in values
        ):
            return DataQualityAvailability(AvailabilityStatus.AVAILABLE)
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
        return DataQualityAvailability(
            status=status,
            reasons=reasons or (AvailabilityReason.NOT_AVAILABLE,),
        )

    @staticmethod
    def _aggregate_quality_status(
        values: tuple[QualityStatus, ...],
    ) -> QualityStatus:
        evaluable = tuple(
            value for value in values if value is not QualityStatus.NOT_AVAILABLE
        )
        if not evaluable:
            return QualityStatus.NOT_AVAILABLE
        priority = (
            QualityStatus.FAILED,
            QualityStatus.WARNING,
            QualityStatus.HEALTHY,
        )
        return next(status for status in priority if status in evaluable)

    @staticmethod
    def _ordered_reasons(
        reasons: Iterable[AvailabilityReason],
    ) -> tuple[AvailabilityReason, ...]:
        included = set(reasons)
        return tuple(reason for reason in AvailabilityReason if reason in included)

    @staticmethod
    def _limit_evidence(
        evidence: tuple[EvidenceItem, ...],
        limit: int | None,
    ) -> tuple[EvidenceItem, ...]:
        return evidence if limit is None else evidence[:limit]

    @staticmethod
    def _failure_evidence(
        issue_type: QualityIssueType,
        module_name: str,
        error: Exception,
    ) -> EvidenceItem:
        return EvidenceItem(
            issue_type=issue_type,
            check_code="EVALUATION_FAILED",
            entity_type=GovernanceScope.SYSTEM.value,
            entity_id=None,
            observed_value=type(error).__name__,
            expected_condition=f"{module_name} provider and rule complete successfully",
            source_type="COMPONENT",
            source_reference_ids=(),
            message=f"{module_name} evaluation is unavailable due to a component error.",
        )

    @classmethod
    def _failure_availability(cls) -> DataQualityAvailability:
        return DataQualityAvailability(
            AvailabilityStatus.NOT_AVAILABLE,
            (AvailabilityReason.EVALUATION_FAILED,),
            "Governance evaluation failed.",
        )

    @classmethod
    def _unavailable_freshness(
        cls,
        analysis_as_of: datetime,
        error: Exception,
    ) -> FreshnessResult:
        evidence = cls._failure_evidence(
            QualityIssueType.FRESHNESS, "Freshness", error
        )
        return FreshnessResult(
            status=QualityStatus.NOT_AVAILABLE,
            availability=cls._failure_availability(),
            delay_seconds=None,
            evidence=(evidence,),
            analysis_as_of=analysis_as_of,
            rule_version=FRESHNESS_RULE_VERSION,
            summary="Freshness evaluation is unavailable.",
        )

    @classmethod
    def _unavailable_completeness(
        cls,
        analysis_as_of: datetime,
        error: Exception,
    ) -> CompletenessResult:
        evidence = cls._failure_evidence(
            QualityIssueType.COMPLETENESS, "Completeness", error
        )
        return CompletenessResult(
            status=QualityStatus.NOT_AVAILABLE,
            availability=cls._failure_availability(),
            coverage_ratio=None,
            evidence=(evidence,),
            analysis_as_of=analysis_as_of,
            rule_version=COMPLETENESS_RULE_VERSION,
            summary="Completeness evaluation is unavailable.",
        )

    @classmethod
    def _unavailable_consistency(
        cls,
        analysis_as_of: datetime,
        error: Exception,
    ) -> ConsistencyResult:
        evidence = cls._failure_evidence(
            QualityIssueType.CONSISTENCY, "Consistency", error
        )
        return ConsistencyResult(
            status=QualityStatus.NOT_AVAILABLE,
            availability=cls._failure_availability(),
            issue_count=1,
            evidence=(evidence,),
            analysis_as_of=analysis_as_of,
            rule_version=CONSISTENCY_RULE_VERSION,
            summary="Consistency evaluation is unavailable.",
        )


__all__ = ["Clock", "DataGovernanceService", "SystemClock"]
