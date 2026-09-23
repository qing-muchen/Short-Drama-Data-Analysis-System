"""Deterministic completeness evaluation for Phase 9 data governance."""

from __future__ import annotations

from decimal import Decimal

from services.data_governance.contracts import (
    COMPLETENESS_RULE_VERSION,
    AvailabilityReason,
    AvailabilityStatus,
    CompletenessResult,
    CompletenessRuleInput,
    DataQualityAvailability,
    EvidenceItem,
    GovernanceScope,
    QualityIssueType,
    QualityStatus,
)


_CRITICAL_FIELDS = frozenset({"drama_id", "drama_code", "drama_name", "status"})


class CompletenessRule:
    """Evaluate field, metric and daily coverage without filling missing data."""

    rule_set_version = COMPLETENESS_RULE_VERSION

    def evaluate(self, rule_input: CompletenessRuleInput) -> CompletenessResult:
        if not isinstance(rule_input, CompletenessRuleInput):
            raise TypeError("rule_input must be CompletenessRuleInput")

        if not (
            rule_input.expected_fields
            or rule_input.metric_coverage
            or rule_input.expected_dates
        ):
            evidence = self._evidence(
                rule_input,
                check_code="NO_COMPLETENESS_SCOPE",
                observed_value=None,
                expected_condition="at least one field, metric, or date to evaluate",
                message="No completeness check scope is available.",
            )
            return CompletenessResult(
                status=QualityStatus.NOT_AVAILABLE,
                availability=DataQualityAvailability(
                    AvailabilityStatus.NOT_AVAILABLE,
                    (AvailabilityReason.NO_DATA,),
                    "Completeness cannot be evaluated without a check scope.",
                ),
                coverage_ratio=None,
                evidence=(evidence,),
                rule_version=self.rule_set_version,
                summary="Completeness is not available.",
            )

        available_fields = set(rule_input.available_fields)
        missing_fields = tuple(
            field_name
            for field_name in rule_input.expected_fields
            if field_name not in available_fields
        )
        missing_metrics = tuple(
            metric_name
            for metric_name, covered in rule_input.metric_coverage
            if not covered
        )
        available_dates = set(rule_input.available_dates)
        missing_dates = tuple(
            business_date
            for business_date in rule_input.expected_dates
            if business_date not in available_dates
        )

        checks = [
            *(field_name not in missing_fields for field_name in rule_input.expected_fields),
            *(covered for _, covered in rule_input.metric_coverage),
            *(business_date not in missing_dates for business_date in rule_input.expected_dates),
            rule_input.platform_relationship_available,
            rule_input.play_count_available,
        ]
        passed_count = sum(checks)
        coverage_ratio = Decimal(passed_count) / Decimal(len(checks))

        missing_items = tuple(
            dict.fromkeys(
                [*(f"field:{name}" for name in missing_fields)]
                + [*(f"metric:{name}" for name in missing_metrics)]
                + [*(f"date:{value.isoformat()}" for value in missing_dates)]
                + (
                    []
                    if rule_input.platform_relationship_available
                    else ["relationship:platform"]
                )
                + ([] if rule_input.play_count_available else ["metric:play_count"])
            )
        )

        evidence: list[EvidenceItem] = []
        if missing_fields:
            evidence.append(
                self._evidence(
                    rule_input,
                    check_code="MISSING_REQUIRED_FIELDS",
                    observed_value=missing_fields,
                    expected_condition="all expected fields are available",
                    message="Required fields are missing.",
                )
            )
        if missing_metrics:
            evidence.append(
                self._evidence(
                    rule_input,
                    check_code="INCOMPLETE_METRIC_COVERAGE",
                    observed_value=missing_metrics,
                    expected_condition="all planned metrics are covered",
                    message="Metric coverage is incomplete.",
                )
            )
        if missing_dates:
            evidence.append(
                self._evidence(
                    rule_input,
                    check_code="INCOMPLETE_TIME_SERIES",
                    observed_value=tuple(value.isoformat() for value in missing_dates),
                    expected_condition="all expected business dates are available",
                    message="The expected time series contains gaps.",
                )
            )
        if not rule_input.platform_relationship_available:
            evidence.append(
                self._evidence(
                    rule_input,
                    check_code="MISSING_PLATFORM_RELATIONSHIP",
                    observed_value=False,
                    expected_condition="an eligible platform relationship exists",
                    message="No eligible platform relationship is available.",
                )
            )
        if not rule_input.play_count_available:
            evidence.append(
                self._evidence(
                    rule_input,
                    check_code="PLAY_COUNT_UNAVAILABLE",
                    observed_value=False,
                    expected_condition="play_count is present and non-negative",
                    message="The required play_count metric is unavailable.",
                )
            )

        critical_missing = bool(_CRITICAL_FIELDS.intersection(missing_fields))
        if (
            critical_missing
            or not rule_input.platform_relationship_available
            or not rule_input.play_count_available
        ):
            status = QualityStatus.FAILED
            summary = "Completeness failed for required identity or metric data."
        elif evidence:
            status = QualityStatus.WARNING
            summary = "Completeness has missing fields, metrics, or dates."
        else:
            status = QualityStatus.HEALTHY
            summary = "All planned completeness checks passed."

        return CompletenessResult(
            status=status,
            availability=DataQualityAvailability(AvailabilityStatus.AVAILABLE),
            coverage_ratio=coverage_ratio,
            missing_items=missing_items,
            evidence=tuple(evidence),
            rule_version=self.rule_set_version,
            summary=summary,
        )

    @staticmethod
    def _evidence(
        rule_input: CompletenessRuleInput,
        *,
        check_code: str,
        observed_value: object,
        expected_condition: str,
        message: str,
    ) -> EvidenceItem:
        return EvidenceItem(
            issue_type=QualityIssueType.COMPLETENESS,
            check_code=check_code,
            entity_type=rule_input.entity_type,
            entity_id=rule_input.entity_id,
            observed_value=observed_value,  # type: ignore[arg-type]
            expected_condition=expected_condition,
            source_type="COVERAGE_INPUT",
            source_reference_ids=(),
            message=message,
        )


__all__ = ["CompletenessRule"]
