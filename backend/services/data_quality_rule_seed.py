"""Explicit, idempotent seed workflow for the approved DQ Rules 1.0 subset."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json
from typing import Any

from sqlalchemy.orm import Session

from repositories.data_quality_repository import DataQualityRuleRepository
from repositories.import_repository import OperationLogRepository

RULE_SET_VERSION = "DQ Rules 1.0"

APPROVED_RULE_DEFINITIONS: tuple[Mapping[str, Any], ...] = (
    {
        "rule_code": "DQ_C_PLAY_COUNT_COVERAGE",
        "rule_version": "1.0",
        "rule_name": "七日播放量覆盖",
        "dimension": "COMPLETENESS",
        "target_entity_type": "SNAPSHOT",
        "evaluator_key": "play_count_coverage_7d",
        "scoring_method": "PASS_RATE",
        "weight": Decimal("1.000000"),
        "severity": "ERROR",
        "configuration": {
            "window_days": 7,
            "window_end_exclusive": "score_date",
            "business_timezone": "Asia/Shanghai",
            "pass_threshold": 100,
            "eligible_drama_statuses": ["SERIALIZING", "COMPLETED"],
            "eligible_platform_status": "ACTIVE",
            "eligible_relation_status": "ONLINE",
            "blocking": False,
        },
        "status": "ACTIVE",
        "description": "Eligible Feed × 前七个完整自然日的播放量覆盖率。",
    },
    {
        "rule_code": "DQ_A_CUMULATIVE_NONNEGATIVE",
        "rule_version": "1.0",
        "rule_name": "累计指标非负",
        "dimension": "ACCURACY",
        "target_entity_type": "SNAPSHOT",
        "evaluator_key": "cumulative_nonnegative_7d",
        "scoring_method": "PASS_RATE",
        "weight": Decimal("1.000000"),
        "severity": "ERROR",
        "configuration": {
            "window_days": 7,
            "window_end_exclusive": "score_date",
            "business_timezone": "Asia/Shanghai",
            "pass_threshold": 100,
            "fields": [
                "play_count",
                "like_count",
                "comment_count",
                "favorite_count",
                "share_count",
            ],
            "optional_null_fields_excluded": True,
            "blocking": False,
        },
        "status": "ACTIVE",
        "description": "七日窗口内现有累计指标值必须非负。",
    },
    {
        "rule_code": "DQ_K_REVISION_CHAIN_VALID",
        "rule_version": "1.0",
        "rule_name": "修订链一致",
        "dimension": "CONSISTENCY",
        "target_entity_type": "SNAPSHOT",
        "evaluator_key": "revision_chain_valid_7d",
        "scoring_method": "PASS_RATE",
        "weight": Decimal("1.000000"),
        "severity": "ERROR",
        "configuration": {
            "window_days": 7,
            "window_end_exclusive": "score_date",
            "business_timezone": "Asia/Shanghai",
            "pass_threshold": 100,
            "include_void_revisions": True,
            "void_fallback_allowed": False,
            "blocking": False,
        },
        "status": "ACTIVE",
        "description": "七日窗口内 Snapshot 的截至 as-of 完整修订链合法。",
    },
    {
        "rule_code": "DQ_T_SNAPSHOT_FRESHNESS",
        "rule_version": "1.0",
        "rule_name": "最新快照及时性",
        "dimension": "TIMELINESS",
        "target_entity_type": "SNAPSHOT",
        "evaluator_key": "snapshot_freshness",
        "scoring_method": "BUCKET_AVERAGE",
        "weight": Decimal("1.000000"),
        "severity": "WARNING",
        "configuration": {
            "business_timezone": "Asia/Shanghai",
            "expected_interval_hours": 24,
            "pass_threshold": 80,
            "age_day_buckets": [
                {"max_days": 1, "score": 100},
                {"max_days": 2, "score": 80},
                {"max_days": 3, "score": 60},
                {"max_days": 7, "score": 40},
                {"max_days": None, "score": 20},
            ],
            "missing_snapshot_score": 0,
            "void_fallback_allowed": False,
            "blocking": False,
        },
        "status": "ACTIVE",
        "description": "Eligible Feed 截至 as-of 的最新有效 Snapshot 时效分。",
    },
)


@dataclass(frozen=True, slots=True)
class RuleSeedResult:
    mode: str
    inserted_count: int
    unchanged_count: int
    configuration_hash: str


class DataQualityRuleSeedConflict(RuntimeError):
    """Existing stable rule identity differs from the reviewed definition."""


def seed_data_quality_rules(
    session: Session,
    *,
    valid_from: datetime,
    apply: bool = False,
    actor_user_id: int | None = None,
) -> RuleSeedResult:
    """Check or insert all four rules atomically; never update an existing version."""

    if apply and (actor_user_id is None or actor_user_id < 1):
        raise ValueError("actor_user_id is required in apply mode")
    try:
        expected = tuple(
            {**dict(definition), "valid_from": valid_from, "valid_to": None}
            for definition in APPROVED_RULE_DEFINITIONS
        )
        identities = tuple(
            (str(item["rule_code"]), str(item["rule_version"])) for item in expected
        )
        rules = DataQualityRuleRepository(session)
        operation_logs = OperationLogRepository(session)
        existing = {
            (rule.rule_code, rule.rule_version): rule
            for rule in rules.list_by_identities(identities)
        }
        missing: list[Mapping[str, Any]] = []
        unchanged = 0
        for definition in expected:
            identity = (
                str(definition["rule_code"]),
                str(definition["rule_version"]),
            )
            current = existing.get(identity)
            if current is None:
                missing.append(definition)
                continue
            differences = _definition_differences(current, definition)
            if differences:
                raise DataQualityRuleSeedConflict(
                    f"Rule {identity[0]}@{identity[1]} differs in: "
                    + ", ".join(differences)
                )

            unchanged += 1

        if apply and missing:
            rules.bulk_create(missing)
            configuration_hash = approved_rule_configuration_hash(
                valid_from=valid_from
            )
            operation_logs.create(
                {
                    "actor_user_id": actor_user_id,
                    "target_user_id": actor_user_id,
                    "operation_type": "DATA_QUALITY_RULE_SEED",
                    "result_status": "SUCCESS",
                    "summary": json.dumps(
                        {
                            "configuration_hash": configuration_hash,
                            "inserted_count": len(missing),
                            "rule_set_version": RULE_SET_VERSION,
                            "valid_from": valid_from.isoformat(
                                timespec="microseconds"
                            ),
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                }
            )
            session.commit()
        elif apply:
            session.commit()
        else:
            session.rollback()
    except Exception:
        session.rollback()
        raise
    return RuleSeedResult(
        mode="APPLY" if apply else "CHECK",
        inserted_count=len(missing) if apply else 0,
        unchanged_count=unchanged,
        configuration_hash=approved_rule_configuration_hash(valid_from=valid_from),
    )


def approved_rule_configuration_hash(*, valid_from: datetime) -> str:
    payload = [
        _json_value({**dict(item), "valid_from": valid_from, "valid_to": None})
        for item in APPROVED_RULE_DEFINITIONS
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _definition_differences(
    entity: DataQualityRule,
    expected: Mapping[str, Any],
) -> tuple[str, ...]:
    compared = tuple(expected)
    return tuple(
        key
        for key in compared
        if _json_value(getattr(entity, key)) != _json_value(expected[key])
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.isoformat(timespec="microseconds")
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


__all__ = (
    "APPROVED_RULE_DEFINITIONS",
    "DataQualityRuleSeedConflict",
    "RULE_SET_VERSION",
    "RuleSeedResult",
    "approved_rule_configuration_hash",
    "seed_data_quality_rules",
)
