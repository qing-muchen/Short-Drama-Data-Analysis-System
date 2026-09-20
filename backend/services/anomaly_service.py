"""Phase 4 anomaly-detection orchestration and transaction boundary."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import json
from typing import Any, Protocol

from sqlalchemy.orm import Session

from analytics.anomaly_detection import (
    ANOMALY_ALGORITHM_VERSION,
    AnomalyDetectionResult as CalculatorDetectionResult,
    AnomalyFinding,
    ENGAGEMENT_RATE_METRIC,
    PLAY_COUNT_METRIC,
    calculate_engagement_rate,
    detect_data_spike_anomaly,
    detect_engagement_rate_anomaly,
    detect_play_count_drop_anomaly,
    detect_play_count_growth_anomaly,
)
from analytics.context import normalize_utc
from repositories.anomaly_repository import AnomalyRepository
from repositories.import_repository import OperationLogRepository
from services.base import BaseService
from services.exceptions import NotFoundException, ValidationException


NO_HISTORY = "NO_HISTORY"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
DATA_QUALITY_BLOCKED = "DATA_QUALITY_BLOCKED"
INSUFFICIENT_METRICS = "INSUFFICIENT_METRICS"
NOT_APPLICABLE = "NOT_APPLICABLE"

ANOMALY_STATUSES = ("OPEN", "ACKNOWLEDGED", "RESOLVED", "IGNORED")
ANOMALY_HISTORY_WINDOW = 9


@dataclass(frozen=True, slots=True)
class AnomalyObservation:
    """One revision-aware platform observation supplied by the history provider."""

    drama_id: int
    observation_date: date
    changed_at: datetime
    platform_id: int
    play_count: int | None
    like_count: int | None
    comment_count: int | None
    favorite_count: int | None
    share_count: int | None
    revision_id: int = 0
    revision_action: str = "INITIAL"
    platform_active: bool = True
    error_count: int = 0
    warning_count: int = 0


class AnomalyHistoryProvider(Protocol):
    """Read-only contract for revision-aware anomaly input data."""

    def get_anomaly_history(
        self,
        *,
        analysis_as_of: datetime,
    ) -> Sequence[AnomalyObservation | Any]: ...


class AnomalyDetector(Protocol):
    """Pure calculator contract used by the Service."""

    def play_count_growth(self, **kwargs: Any) -> CalculatorDetectionResult: ...

    def play_count_drop(self, **kwargs: Any) -> CalculatorDetectionResult: ...

    def engagement_rate(self, **kwargs: Any) -> CalculatorDetectionResult: ...

    def data_spike(self, **kwargs: Any) -> CalculatorDetectionResult: ...


class _DefaultAnomalyDetector:
    """Adapter around the four public pure Calculator functions."""

    play_count_growth = staticmethod(detect_play_count_growth_anomaly)
    play_count_drop = staticmethod(detect_play_count_drop_anomaly)
    engagement_rate = staticmethod(detect_engagement_rate_anomaly)
    data_spike = staticmethod(detect_data_spike_anomaly)


@dataclass(frozen=True, slots=True)
class AnomalyDetectionServiceResult:
    """Summary returned after one atomic detection batch."""

    analysis_as_of: datetime
    algorithm_version: str
    detected_count: int
    skipped_count: int
    skip_reasons: dict[str, int]


# The public Service result name follows the Phase 4 contract. The Calculator
# keeps its own same-named result type in analytics.anomaly_detection.
AnomalyDetectionResult = AnomalyDetectionServiceResult


class AnomalyService(BaseService):
    """Prepare as-of histories, call the pure detector, persist, and audit."""

    def __init__(
        self,
        session: Session,
        history: AnomalyHistoryProvider,
        anomalies: AnomalyRepository,
        operation_logs: OperationLogRepository,
        *,
        detector: AnomalyDetector | None = None,
    ) -> None:
        super().__init__(session, anomalies, operation_logs)
        self.history = history
        self.anomalies = anomalies
        self.operation_logs = operation_logs
        self.detector = detector or _DefaultAnomalyDetector()

    def detect_anomalies(
        self,
        analysis_as_of: datetime | None = None,
        *,
        operator_user_id: int,
        request_id: str | None = None,
    ) -> AnomalyDetectionServiceResult:
        """Detect one as-of batch and commit findings plus one operation log."""

        cutoff = normalize_utc(analysis_as_of or datetime.now(timezone.utc))
        skipped_reasons: Counter[str] = Counter()
        findings: list[AnomalyFinding] = []

        with self.transaction():
            raw_history = self.history.get_anomaly_history(
                analysis_as_of=cutoff,
            )
            grouped = self._prepare_histories(raw_history, cutoff=cutoff)
            if not raw_history or not grouped:
                skipped_reasons[NO_HISTORY] += 1
            for drama_id, observations in grouped.items():
                if self._has_quality_error(observations):
                    skipped_reasons[DATA_QUALITY_BLOCKED] += 1
                    continue
                points, reason = self._build_daily_points(observations)
                if reason is not None:
                    skipped_reasons[reason] += 1
                    continue
                drama_findings, drama_skips = self._detect_drama(
                    drama_id=drama_id,
                    points=points,
                    analysis_as_of=cutoff,
                )
                findings.extend(drama_findings)
                skipped_reasons.update(drama_skips)

            self.anomalies.save_anomalies(findings)
            self._audit_detection(
                operator_user_id=operator_user_id,
                request_id=request_id,
                analysis_as_of=cutoff,
                detected_count=len(findings),
                skipped_count=sum(skipped_reasons.values()),
                skipped_reasons=skipped_reasons,
            )

        return AnomalyDetectionServiceResult(
            analysis_as_of=cutoff,
            algorithm_version=ANOMALY_ALGORITHM_VERSION,
            detected_count=len(findings),
            skipped_count=sum(skipped_reasons.values()),
            skip_reasons=dict(sorted(skipped_reasons.items())),
        )

    def get_anomalies(self, **filters: Any) -> Any:
        """Delegate global anomaly listing without recalculation or sorting."""

        return self.read(self.anomalies.get_anomalies, **filters)

    def get_drama_anomalies(self, drama_id: int, *, limit: int | None = None) -> list[Any]:
        """Delegate one drama's anomaly history."""

        return self.read(
            self.anomalies.get_by_drama,
            drama_id=drama_id,
            limit=limit,
        )

    def get_latest_anomalies(self) -> list[Any]:
        """Delegate latest detection-snapshot lookup."""

        return self.read(self.anomalies.get_latest_anomalies)

    def get_statistics(self) -> Any:
        """Delegate persisted anomaly statistics."""

        return self.read(self.anomalies.get_statistics)

    def update_status(
        self,
        anomaly_id: int,
        new_status: str,
        *,
        operator_user_id: int,
        request_id: str | None = None,
    ) -> Any:
        """Update one status and write its audit event atomically."""

        if new_status not in ANOMALY_STATUSES:
            raise ValidationException(
                "Unsupported anomaly status",
                details={"status": new_status},
            )
        with self.transaction():
            entity = self.anomalies.update_status(
                anomaly_id=anomaly_id,
                new_status=new_status,
            )
            if entity is None:
                raise NotFoundException(
                    "Anomaly was not found",
                    details={"anomaly_id": anomaly_id},
                )
            summary = json.dumps(
                {
                    "anomaly_id": anomaly_id,
                    "new_status": new_status,
                },
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            values: dict[str, Any] = {
                "actor_user_id": operator_user_id,
                "target_drama_id": int(entity.drama_id),
                "operation_type": "ANOMALY_STATUS_UPDATE",
                "result_status": "SUCCESS",
                "summary": summary,
            }
            if request_id is not None:
                values["request_id"] = request_id
            self.operation_logs.create(values)
        return entity

    @staticmethod
    def _prepare_histories(
        observations: Sequence[AnomalyObservation | Any],
        *,
        cutoff: datetime,
    ) -> dict[int, list[AnomalyObservation]]:
        latest: dict[tuple[int, int, date], AnomalyObservation] = {}
        for raw in observations:
            item = AnomalyService._coerce_observation(raw)
            changed_at = normalize_utc(item.changed_at)
            if changed_at > cutoff:
                continue
            if item.revision_action not in {"INITIAL", "CORRECTION", "VOID"}:
                continue
            key = (item.drama_id, item.platform_id, item.observation_date)
            previous = latest.get(key)
            if previous is None or (changed_at, item.revision_id) > (
                normalize_utc(previous.changed_at),
                previous.revision_id,
            ):
                latest[key] = AnomalyObservation(
                    drama_id=item.drama_id,
                    observation_date=item.observation_date,
                    changed_at=changed_at,
                    platform_id=item.platform_id,
                    play_count=item.play_count,
                    like_count=item.like_count,
                    comment_count=item.comment_count,
                    favorite_count=item.favorite_count,
                    share_count=item.share_count,
                    revision_id=item.revision_id,
                    revision_action=item.revision_action,
                    platform_active=item.platform_active,
                    error_count=item.error_count,
                    warning_count=item.warning_count,
                )
        grouped: dict[int, list[AnomalyObservation]] = defaultdict(list)
        for item in latest.values():
            if item.revision_action == "VOID" or not item.platform_active:
                continue
            grouped[item.drama_id].append(item)
        for drama_id in grouped:
            grouped[drama_id].sort(key=lambda item: item.observation_date)
        return dict(grouped)

    @staticmethod
    def _coerce_observation(raw: AnomalyObservation | Any) -> AnomalyObservation:
        if isinstance(raw, AnomalyObservation):
            return raw
        snapshot_time = getattr(raw, "snapshot_time", None)
        observation_date = getattr(raw, "observation_date", None)
        if observation_date is None and snapshot_time is not None:
            observation_date = snapshot_time.date()
        changed_at = getattr(raw, "changed_at", None) or snapshot_time
        if observation_date is None or changed_at is None:
            raise ValidationException(
                "Anomaly history observation is missing its date",
                details={"reason": INSUFFICIENT_METRICS},
            )
        return AnomalyObservation(
            drama_id=int(raw.drama_id),
            observation_date=observation_date,
            changed_at=changed_at,
            platform_id=int(getattr(raw, "platform_id", 0)),
            play_count=getattr(raw, "play_count", None),
            like_count=getattr(raw, "like_count", None),
            comment_count=getattr(raw, "comment_count", None),
            favorite_count=getattr(raw, "favorite_count", None),
            share_count=getattr(raw, "share_count", None),
            revision_id=int(
                getattr(raw, "revision_id", getattr(raw, "snapshot_revision_id", 0))
            ),
            revision_action=str(getattr(raw, "revision_action", "INITIAL")),
            platform_active=AnomalyService._platform_is_active(raw),
            error_count=int(
                max(
                    getattr(raw, "error_count", getattr(raw, "excluded_error_count", 0)),
                    1 if getattr(raw, "quality_status", "") == "ERROR" else 0,
                )
            ),
            warning_count=int(
                max(
                    getattr(raw, "warning_count", 0),
                    1 if getattr(raw, "quality_status", "") == "WARNING" else 0,
                )
            ),
        )

    @staticmethod
    def _platform_is_active(raw: Any) -> bool:
        explicit = getattr(raw, "platform_active", None)
        if explicit is not None:
            return bool(explicit)
        platform_status = getattr(raw, "platform_status", None)
        drama_platform_status = getattr(raw, "drama_platform_status", None)
        if platform_status is None and drama_platform_status is None:
            return True
        return platform_status == "ACTIVE" and drama_platform_status == "RELEASED"

    @staticmethod
    def _has_quality_error(observations: Sequence[AnomalyObservation]) -> bool:
        return any(item.error_count > 0 for item in observations)

    @staticmethod
    def _build_daily_points(
        observations: Sequence[AnomalyObservation],
    ) -> tuple[list[AnomalyObservation], str | None]:
        by_date: dict[date, list[AnomalyObservation]] = defaultdict(list)
        for item in observations:
            by_date[item.observation_date].append(item)
        dates = sorted(by_date)
        if not dates:
            return [], NO_HISTORY
        if len(dates) < ANOMALY_HISTORY_WINDOW:
            return [], INSUFFICIENT_HISTORY
        expected = [
            dates[-1] - timedelta(days=offset)
            for offset in range(ANOMALY_HISTORY_WINDOW - 1, -1, -1)
        ]
        if dates[-ANOMALY_HISTORY_WINDOW:] != expected:
            return [], INSUFFICIENT_HISTORY
        points: list[AnomalyObservation] = []
        for day in expected:
            rows = by_date[day]
            if any(
                value is None
                for row in rows
                for value in (
                    row.play_count,
                    row.like_count,
                    row.comment_count,
                    row.favorite_count,
                    row.share_count,
                )
            ):
                return [], INSUFFICIENT_METRICS
            points.append(
                AnomalyObservation(
                    drama_id=rows[0].drama_id,
                    observation_date=day,
                    changed_at=max(row.changed_at for row in rows),
                    platform_id=0,
                    play_count=sum(int(row.play_count or 0) for row in rows),
                    like_count=sum(int(row.like_count or 0) for row in rows),
                    comment_count=sum(int(row.comment_count or 0) for row in rows),
                    favorite_count=sum(int(row.favorite_count or 0) for row in rows),
                    share_count=sum(int(row.share_count or 0) for row in rows),
                    error_count=max(row.error_count for row in rows),
                    warning_count=sum(row.warning_count for row in rows),
                )
            )
        return points, None

    def _detect_drama(
        self,
        *,
        drama_id: int,
        points: Sequence[AnomalyObservation],
        analysis_as_of: datetime,
    ) -> tuple[list[AnomalyFinding], Counter[str]]:
        if len(points) != ANOMALY_HISTORY_WINDOW:
            return [], Counter({INSUFFICIENT_HISTORY: 1})
        play_counts = [int(item.play_count or 0) for item in points]
        increments = [
            play_counts[index] - play_counts[index - 1]
            for index in range(1, len(play_counts))
        ]
        if any(value < 0 for value in increments):
            return [], Counter({DATA_QUALITY_BLOCKED: 1})
        rates = [
            self._engagement_rate(item)
            for item in points
        ]
        findings: list[AnomalyFinding] = []
        skipped: Counter[str] = Counter()
        calculations = (
            self.detector.play_count_growth(
                drama_id=drama_id,
                historical_growth=increments[:-1],
                current_growth=increments[-1],
                analysis_as_of=analysis_as_of,
            ),
            self.detector.play_count_drop(
                drama_id=drama_id,
                historical_growth=increments[:-1],
                current_growth=increments[-1],
                analysis_as_of=analysis_as_of,
            ),
            self.detector.engagement_rate(
                drama_id=drama_id,
                historical_rates=rates[:-1],
                current_rate=rates[-1],
                play_count=play_counts[-1],
                analysis_as_of=analysis_as_of,
            ),
            self.detector.data_spike(
                drama_id=drama_id,
                metric_type=PLAY_COUNT_METRIC,
                historical_values=play_counts[:-1],
                current_value=play_counts[-1],
                analysis_as_of=analysis_as_of,
            ),
            self.detector.data_spike(
                drama_id=drama_id,
                metric_type=ENGAGEMENT_RATE_METRIC,
                historical_values=rates[:-1],
                current_value=rates[-1],
                play_count=play_counts[-1],
                analysis_as_of=analysis_as_of,
            ),
        )
        for result in calculations:
            if result.finding is not None:
                findings.append(result.finding)
            elif result.status == "INSUFFICIENT_HISTORY":
                skipped[INSUFFICIENT_HISTORY] += 1
            elif result.status == "NOT_APPLICABLE":
                skipped[NOT_APPLICABLE] += 1
        return findings, skipped

    @staticmethod
    def _engagement_rate(item: AnomalyObservation) -> Decimal:
        if not item.play_count:
            return Decimal("0")
        return calculate_engagement_rate(
            play_count=item.play_count,
            like_count=item.like_count or 0,
            comment_count=item.comment_count or 0,
            favorite_count=item.favorite_count or 0,
            share_count=item.share_count or 0,
        )

    def _audit_detection(
        self,
        *,
        operator_user_id: int,
        request_id: str | None,
        analysis_as_of: datetime,
        detected_count: int,
        skipped_count: int,
        skipped_reasons: Counter[str],
    ) -> None:
        detail = {
            "algorithm_version": ANOMALY_ALGORITHM_VERSION,
            "analysis_as_of": analysis_as_of.isoformat(),
            "detected_count": detected_count,
            "skipped_count": skipped_count,
            "skipped_reasons": dict(sorted(skipped_reasons.items())),
        }
        values: dict[str, Any] = {
            "actor_user_id": operator_user_id,
            "target_user_id": operator_user_id,
            "operation_type": "ANOMALY_DETECT",
            "result_status": "SUCCESS",
            "summary": json.dumps(
                detail,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ),
        }
        if request_id is not None:
            values["request_id"] = request_id
        self.operation_logs.create(values)


__all__ = (
    "ANOMALY_HISTORY_WINDOW",
    "ANOMALY_STATUSES",
    "AnomalyDetectionResult",
    "AnomalyDetectionServiceResult",
    "AnomalyHistoryProvider",
    "AnomalyObservation",
    "AnomalyService",
    "DATA_QUALITY_BLOCKED",
    "INSUFFICIENT_HISTORY",
    "INSUFFICIENT_METRICS",
    "NO_HISTORY",
    "NOT_APPLICABLE",
)
