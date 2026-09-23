"""Deterministic consistency evaluation for Phase 9 data governance."""

from __future__ import annotations

from services.data_governance.contracts import (
    CONSISTENCY_RULE_VERSION,
    AvailabilityReason,
    AvailabilityStatus,
    ConsistencyCheckInput,
    ConsistencyResult,
    ConsistencyRuleInput,
    DataQualityAvailability,
    EvidenceItem,
    GovernanceScope,
    QualityIssueType,
    QualityStatus,
)


class ConsistencyRule:
    """Evaluate preloaded relationship and revision consistency facts."""

    rule_set_version = CONSISTENCY_RULE_VERSION

    def evaluate(self, rule_input: ConsistencyRuleInput) -> ConsistencyResult:
        if not isinstance(rule_input, ConsistencyRuleInput):
            raise TypeError("rule_input must be ConsistencyRuleInput")

        all_checks = rule_input.relationship_checks + rule_input.revision_checks
        if not all_checks:
            evidence = EvidenceItem(
                issue_type=QualityIssueType.CONSISTENCY,
                check_code="NO_CONSISTENCY_SCOPE",
                entity_type=GovernanceScope.SYSTEM.value,
                entity_id=None,
                observed_value=None,
                expected_condition="at least one relationship or revision check",
                source_type="CONSISTENCY_INPUT",
                source_reference_ids=(),
                message="No consistency checks are available.",
            )
            return ConsistencyResult(
                status=QualityStatus.NOT_AVAILABLE,
                availability=DataQualityAvailability(
                    AvailabilityStatus.NOT_AVAILABLE,
                    (AvailabilityReason.NO_DATA,),
                    "Consistency cannot be evaluated without check inputs.",
                ),
                issue_count=1,
                evidence=(evidence,),
                analysis_as_of=rule_input.as_of_timestamp,
                rule_version=self.rule_set_version,
                summary="Consistency is not available.",
            )

        evidence: list[EvidenceItem] = []
        has_failed_revision = False
        has_failed_as_of = False
        has_unresolved = False

        revision_ids = {id(check) for check in rule_input.revision_checks}
        for check in all_checks:
            if check.consistent is True:
                continue
            unresolved = check.consistent is None
            has_unresolved = has_unresolved or unresolved
            check_code = check.check_code.upper()
            if not unresolved and id(check) in revision_ids:
                has_failed_revision = True
            if not unresolved and "AS_OF" in check_code:
                has_failed_as_of = True
            evidence.append(self._evidence(check, unresolved=unresolved))

        if not evidence:
            return ConsistencyResult(
                status=QualityStatus.HEALTHY,
                availability=DataQualityAvailability(AvailabilityStatus.AVAILABLE),
                issue_count=0,
                analysis_as_of=rule_input.as_of_timestamp,
                rule_version=self.rule_set_version,
                summary="All planned consistency checks passed.",
            )

        if has_unresolved:
            availability = DataQualityAvailability(
                AvailabilityStatus.PARTIAL,
                (AvailabilityReason.UNRESOLVED_RELATION,),
                "Some weak references could not be resolved.",
            )
        else:
            availability = DataQualityAvailability(AvailabilityStatus.AVAILABLE)

        if has_failed_revision or has_failed_as_of:
            status = QualityStatus.FAILED
            summary = "Revision or analysis cutoff consistency failed."
        else:
            status = QualityStatus.WARNING
            summary = "Relationship consistency requires attention."

        return ConsistencyResult(
            status=status,
            availability=availability,
            issue_count=len(evidence),
            evidence=tuple(evidence),
            analysis_as_of=rule_input.as_of_timestamp,
            rule_version=self.rule_set_version,
            summary=summary,
        )

    @staticmethod
    def _evidence(
        check: ConsistencyCheckInput,
        *,
        unresolved: bool,
    ) -> EvidenceItem:
        if unresolved:
            check_code = f"{check.check_code}_UNRESOLVED"
            message = f"{check.check_code} could not be evaluated."
        else:
            check_code = check.check_code
            message = f"{check.check_code} is inconsistent."
        return EvidenceItem(
            issue_type=QualityIssueType.CONSISTENCY,
            check_code=check_code,
            entity_type=check.entity_type,
            entity_id=check.entity_id,
            observed_value=check.observed_value,
            expected_condition=check.expected_condition,
            source_type=check.source_type,
            source_reference_ids=check.source_reference_ids,
            message=message,
        )


__all__ = ["ConsistencyRule"]
