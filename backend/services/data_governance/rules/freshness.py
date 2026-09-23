"""Deterministic freshness evaluation for Phase 9 data governance."""

from __future__ import annotations

from services.data_governance.contracts import (
    FRESHNESS_RULE_VERSION,
    AvailabilityReason,
    AvailabilityStatus,
    DataQualityAvailability,
    EvidenceItem,
    FreshnessResult,
    FreshnessRuleInput,
    QualityIssueType,
    QualityStatus,
)


class FreshnessRule:
    """Evaluate an already-loaded timestamp without performing any I/O."""

    rule_set_version = FRESHNESS_RULE_VERSION

    def evaluate(self, rule_input: FreshnessRuleInput) -> FreshnessResult:
        if not isinstance(rule_input, FreshnessRuleInput):
            raise TypeError("rule_input must be FreshnessRuleInput")

        if rule_input.latest_timestamp is None:
            evidence = self._evidence(
                rule_input,
                check_code="NO_VISIBLE_DATA",
                observed_value=None,
                expected_condition="a visible timestamp not later than analysis_as_of",
                message="No visible data timestamp is available for evaluation.",
            )
            return FreshnessResult(
                status=QualityStatus.NOT_AVAILABLE,
                availability=DataQualityAvailability(
                    AvailabilityStatus.NOT_AVAILABLE,
                    (AvailabilityReason.NO_DATA,),
                    "Freshness cannot be evaluated without a visible timestamp.",
                ),
                delay_seconds=None,
                evidence=(evidence,),
                analysis_as_of=rule_input.current_timestamp,
                rule_version=self.rule_set_version,
                summary="Freshness is not available.",
            )

        delay_seconds = int(
            (rule_input.current_timestamp - rule_input.latest_timestamp).total_seconds()
        )
        warning_seconds = int(rule_input.threshold.total_seconds())
        failure_seconds = int(rule_input.failure_threshold.total_seconds())

        if delay_seconds < 0:
            evidence = self._evidence(
                rule_input,
                check_code="FUTURE_TIMESTAMP",
                observed_value=(
                    rule_input.latest_timestamp.isoformat(),
                    delay_seconds,
                ),
                expected_condition="latest_timestamp <= current_timestamp",
                message="The latest data timestamp is later than the analysis cutoff.",
            )
            return FreshnessResult(
                status=QualityStatus.FAILED,
                availability=DataQualityAvailability(AvailabilityStatus.AVAILABLE),
                delay_seconds=delay_seconds,
                evidence=(evidence,),
                analysis_as_of=rule_input.current_timestamp,
                rule_version=self.rule_set_version,
                summary="Freshness failed because a future timestamp was observed.",
            )

        if delay_seconds <= warning_seconds:
            return FreshnessResult(
                status=QualityStatus.HEALTHY,
                availability=DataQualityAvailability(AvailabilityStatus.AVAILABLE),
                delay_seconds=delay_seconds,
                analysis_as_of=rule_input.current_timestamp,
                rule_version=self.rule_set_version,
                summary="Data is within the freshness threshold.",
            )

        if delay_seconds <= failure_seconds:
            status = QualityStatus.WARNING
            check_code = "DATA_DELAYED"
            expected = f"delay_seconds <= {warning_seconds}"
            message = "Data is later than the freshness warning threshold."
            summary = "Data freshness requires attention."
        else:
            status = QualityStatus.FAILED
            check_code = "DATA_STALE"
            expected = f"delay_seconds <= {failure_seconds}"
            message = "Data is later than the freshness failure threshold."
            summary = "Data freshness failed."

        evidence = self._evidence(
            rule_input,
            check_code=check_code,
            observed_value=(
                rule_input.latest_timestamp.isoformat(),
                delay_seconds,
                warning_seconds,
                failure_seconds,
            ),
            expected_condition=expected,
            message=message,
        )
        return FreshnessResult(
            status=status,
            availability=DataQualityAvailability(AvailabilityStatus.AVAILABLE),
            delay_seconds=delay_seconds,
            evidence=(evidence,),
            analysis_as_of=rule_input.current_timestamp,
            rule_version=self.rule_set_version,
            summary=summary,
        )

    @staticmethod
    def _evidence(
        rule_input: FreshnessRuleInput,
        *,
        check_code: str,
        observed_value: object,
        expected_condition: str,
        message: str,
    ) -> EvidenceItem:
        return EvidenceItem(
            issue_type=QualityIssueType.FRESHNESS,
            check_code=check_code,
            entity_type=rule_input.entity_type,
            entity_id=rule_input.entity_id,
            observed_value=observed_value,  # type: ignore[arg-type]
            expected_condition=expected_condition,
            source_type="TIMESTAMP",
            source_reference_ids=(rule_input.entity_id,),
            message=message,
        )


__all__ = ["FreshnessRule"]
