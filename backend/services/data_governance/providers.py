"""Read-only mappings from governance repository projections to rule inputs."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Protocol, Sequence
from zoneinfo import ZoneInfo

from repositories.data_governance_repository import (
    ActionSourceReadRecord,
    ActionStatusReadRecord,
    CompletenessTargetRecord,
    FreshnessReadRecord,
    LineageReadRecord,
    MetricCoverageReadRecord,
    RevisionReadRecord,
)
from services.data_governance.contracts import (
    CompletenessRuleInput,
    ConsistencyCheckInput,
    ConsistencyRuleInput,
    FreshnessRuleInput,
)


BUSINESS_TIMEZONE = ZoneInfo("Asia/Shanghai")
EXPECTED_DRAMA_FIELDS = ("drama_id", "drama_code", "drama_name", "status")


class DataGovernanceReadRepository(Protocol):
    def list_freshness_records(
        self, *, analysis_as_of: datetime
    ) -> tuple[FreshnessReadRecord, ...]: ...

    def list_completeness_targets(
        self, *, analysis_as_of: datetime
    ) -> tuple[CompletenessTargetRecord, ...]: ...

    def list_metric_coverage_records(
        self,
        *,
        drama_platform_ids: Sequence[int],
        start_time: datetime,
        end_time: datetime,
        analysis_as_of: datetime,
    ) -> tuple[MetricCoverageReadRecord, ...]: ...

    def list_action_source_records(
        self, *, analysis_as_of: datetime
    ) -> tuple[ActionSourceReadRecord, ...]: ...

    def list_action_status_records(
        self, *, analysis_as_of: datetime
    ) -> tuple[ActionStatusReadRecord, ...]: ...

    def list_lineage_records(
        self, *, analysis_as_of: datetime
    ) -> tuple[LineageReadRecord, ...]: ...

    def list_revision_records(
        self, *, analysis_as_of: datetime
    ) -> tuple[RevisionReadRecord, ...]: ...


class FreshnessProvider:
    """Map latest visible feed timestamps without evaluating freshness."""

    def __init__(self, repository: DataGovernanceReadRepository) -> None:
        self.repository = repository

    def get_rule_inputs(
        self,
        *,
        analysis_as_of: datetime,
    ) -> tuple[FreshnessRuleInput, ...]:
        cutoff = _aware_utc(analysis_as_of)
        records = self.repository.list_freshness_records(analysis_as_of=cutoff)
        return tuple(
            FreshnessRuleInput(
                entity_type="METRIC_FEED",
                entity_id=record.drama_platform_id,
                latest_timestamp=(
                    _aware_utc(record.latest_snapshot_time)
                    if record.latest_snapshot_time is not None
                    else None
                ),
                current_timestamp=cutoff,
            )
            for record in records
        )


class CompletenessProvider:
    """Prepare field, metric and seven-day coverage facts for rules."""

    def __init__(
        self,
        repository: DataGovernanceReadRepository,
        *,
        business_timezone: ZoneInfo = BUSINESS_TIMEZONE,
    ) -> None:
        self.repository = repository
        self.business_timezone = business_timezone

    def get_rule_inputs(
        self,
        *,
        analysis_as_of: datetime,
    ) -> tuple[CompletenessRuleInput, ...]:
        cutoff = _aware_utc(analysis_as_of)
        expected_dates, start_time, end_time = self._window(cutoff)
        targets = self.repository.list_completeness_targets(
            analysis_as_of=cutoff
        )
        valid_platform_ids = tuple(
            target.drama_platform_id
            for target in targets
            if target.drama_platform_id is not None
            and target.platform_id is not None
        )
        coverage_records = self.repository.list_metric_coverage_records(
            drama_platform_ids=valid_platform_ids,
            start_time=start_time,
            end_time=end_time,
            analysis_as_of=cutoff,
        )
        records_by_platform: dict[int, list[MetricCoverageReadRecord]] = defaultdict(
            list
        )
        for record in coverage_records:
            records_by_platform[record.drama_platform_id].append(record)

        inputs: list[CompletenessRuleInput] = []
        for target in targets:
            relation_available = (
                target.drama_platform_id is not None
                and target.platform_id is not None
            )
            records = (
                records_by_platform.get(target.drama_platform_id, [])
                if target.drama_platform_id is not None
                else []
            )
            available_dates = tuple(
                sorted(
                    {
                        self._business_date(record.snapshot_time)
                        for record in records
                        if record.play_count is not None and record.play_count >= 0
                    }
                )
            )
            expected_date_set = set(expected_dates)
            play_count_available = bool(expected_dates) and expected_date_set.issubset(
                available_dates
            )
            available_fields = tuple(
                field_name
                for field_name, value in (
                    ("drama_id", target.drama_id),
                    ("drama_code", target.drama_code),
                    ("drama_name", target.drama_name),
                    ("status", target.drama_status),
                )
                if _is_present(value)
            )
            inputs.append(
                CompletenessRuleInput(
                    expected_fields=EXPECTED_DRAMA_FIELDS,
                    available_fields=available_fields,
                    metric_coverage=(("play_count", play_count_available),),
                    entity_type=(
                        "DRAMA_PLATFORM" if relation_available else "DRAMA"
                    ),
                    entity_id=(
                        target.drama_platform_id
                        if relation_available
                        else target.drama_id
                    ),
                    expected_dates=expected_dates,
                    available_dates=available_dates,
                    platform_relationship_available=relation_available,
                    play_count_available=play_count_available,
                )
            )
        return tuple(inputs)

    def _window(
        self,
        analysis_as_of: datetime,
    ) -> tuple[tuple[date, ...], datetime, datetime]:
        local_cutoff = analysis_as_of.astimezone(self.business_timezone)
        current_business_date = local_cutoff.date()
        expected_dates = tuple(
            current_business_date - timedelta(days=offset)
            for offset in range(7, 0, -1)
        )
        start_local = datetime.combine(
            expected_dates[0], time.min, tzinfo=self.business_timezone
        )
        end_local = datetime.combine(
            current_business_date, time.min, tzinfo=self.business_timezone
        )
        return (
            expected_dates,
            start_local.astimezone(timezone.utc),
            end_local.astimezone(timezone.utc),
        )

    def _business_date(self, value: datetime) -> date:
        return _aware_utc(value).astimezone(self.business_timezone).date()


class ConsistencyProvider:
    """Map relationship, revision and cutoff facts to consistency checks."""

    def __init__(self, repository: DataGovernanceReadRepository) -> None:
        self.repository = repository

    def get_rule_input(
        self,
        *,
        analysis_as_of: datetime,
    ) -> ConsistencyRuleInput:
        cutoff = _aware_utc(analysis_as_of)
        relationship_checks: list[ConsistencyCheckInput] = []

        for record in self.repository.list_action_source_records(
            analysis_as_of=cutoff
        ):
            relationship_checks.append(self._action_source_check(record))

        for record in self.repository.list_action_status_records(
            analysis_as_of=cutoff
        ):
            relationship_checks.append(self._action_status_check(record))

        for record in self.repository.list_lineage_records(
            analysis_as_of=cutoff
        ):
            relationship_checks.extend(self._lineage_checks(record))

        revision_checks = tuple(
            self._revision_check(record)
            for record in self.repository.list_revision_records(
                analysis_as_of=cutoff
            )
        )
        return ConsistencyRuleInput(
            relationship_checks=tuple(relationship_checks),
            revision_checks=revision_checks,
            as_of_timestamp=cutoff,
        )

    @staticmethod
    def _action_source_check(
        record: ActionSourceReadRecord,
    ) -> ConsistencyCheckInput:
        references = (
            (record.source_reference_id,)
            if record.source_reference_id is not None
            else ()
        )
        return ConsistencyCheckInput(
            check_code="ACTION_SOURCE_REFERENCE",
            entity_type="OPERATION_ACTION_SOURCE",
            entity_id=record.source_id,
            consistent=record.target_exists,
            source_type=record.source_type,
            source_reference_ids=references,
            observed_value=(record.source_type, record.source_reference_id),
            expected_condition="the logical action source reference exists",
        )

    @staticmethod
    def _action_status_check(
        record: ActionStatusReadRecord,
    ) -> ConsistencyCheckInput:
        return ConsistencyCheckInput(
            check_code="ACTION_STATUS_HISTORY",
            entity_type="OPERATION_ACTION",
            entity_id=record.action_id,
            consistent=(
                None
                if record.latest_history_status is None
                else record.current_status == record.latest_history_status
            ),
            source_type="ACTION_HISTORY",
            source_reference_ids=(
                (record.latest_history_id,)
                if record.latest_history_id is not None
                else ()
            ),
            observed_value=(record.current_status, record.latest_history_status),
            expected_condition="current action status equals latest status event",
        )

    @staticmethod
    def _lineage_checks(
        record: LineageReadRecord,
    ) -> tuple[ConsistencyCheckInput, ...]:
        common = {
            "entity_type": "ANALYSIS_LINEAGE",
            "entity_id": record.lineage_id,
            "source_type": record.source_type,
            "source_reference_ids": (record.source_id,),
        }
        return (
            ConsistencyCheckInput(
                check_code="LINEAGE_TARGET_EXISTS",
                consistent=record.target_exists,
                observed_value=(record.target_type, record.target_id),
                expected_condition="the lineage target exists",
                **common,
            ),
            ConsistencyCheckInput(
                check_code="LINEAGE_TARGET_AS_OF_MATCHES",
                consistent=record.target_as_of_matches,
                observed_value=record.lineage_analysis_as_of.isoformat(),
                expected_condition="lineage and target analysis_as_of match",
                **common,
            ),
            ConsistencyCheckInput(
                check_code="LINEAGE_SOURCE_EXISTS",
                consistent=record.source_exists,
                observed_value=(record.source_type, record.source_id),
                expected_condition="the resolvable lineage source exists",
                **common,
            ),
            ConsistencyCheckInput(
                check_code="LINEAGE_SOURCE_AS_OF_VISIBLE",
                consistent=record.source_visible_as_of,
                observed_value=record.lineage_analysis_as_of.isoformat(),
                expected_condition="source visible time is not later than target as_of",
                **common,
            ),
        )

    @staticmethod
    def _revision_check(record: RevisionReadRecord) -> ConsistencyCheckInput:
        if record.version_no == 1:
            consistent = (
                record.revision_action == "INITIAL"
                and record.previous_revision_id is None
            )
        else:
            consistent = (
                record.revision_action in {"CORRECTION", "VOID"}
                and record.previous_revision_id is not None
                and record.previous_snapshot_id == record.snapshot_id
                and record.previous_version_no == record.version_no - 1
            )
        references = tuple(
            value
            for value in (
                record.snapshot_revision_id,
                record.previous_revision_id,
            )
            if value is not None
        )
        return ConsistencyCheckInput(
            check_code="SNAPSHOT_REVISION_CHAIN",
            entity_type="SNAPSHOT_REVISION",
            entity_id=record.snapshot_revision_id,
            consistent=consistent,
            source_type="SNAPSHOT",
            source_reference_ids=references,
            observed_value=(
                record.snapshot_id,
                record.version_no,
                record.revision_action,
                record.previous_revision_id,
                record.previous_snapshot_id,
                record.previous_version_no,
            ),
            expected_condition="revision action and previous revision form a valid chain",
        )


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _is_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


__all__ = [
    "BUSINESS_TIMEZONE",
    "CompletenessProvider",
    "ConsistencyProvider",
    "DataGovernanceReadRepository",
    "FreshnessProvider",
]
