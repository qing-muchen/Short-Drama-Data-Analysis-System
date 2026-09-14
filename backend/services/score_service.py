"""Composite Score V1.0 business orchestration and transaction boundary."""

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
import json
from math import isfinite
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from analytics.composite_score import (
    COMPOSITE_SCORE_VERSION,
    CompositeScoreValidationError,
    calculate_composite_score,
    calculate_growth_score,
    calculate_lifecycle_stage_score,
    calculate_min_max_score,
    round_half_up,
)
from analytics.context import AnalysisContext
from analytics.metrics import MetricResult
from repositories.base import Page
from repositories.drama_repository import DramaRepository
from repositories.import_repository import OperationLogRepository
from repositories.score_repository import ScoreRepository
from services.analytics_service import AnalyticsService
from services.base import BaseService
from services.exceptions import ValidationException

SCORE_SCOPE_TYPE = "ALL"
SCORE_SCOPE_ID = 0
SCORE_TIME_WINDOW = "7D"
SCORE_GRANULARITY = "DRAMA_OVERALL"
BUSINESS_TIME_ZONE = ZoneInfo("Asia/Shanghai")

NO_VALID_SNAPSHOT = "NO_VALID_SNAPSHOT"
INCOMPLETE_METRICS = "INCOMPLETE_METRICS"
ZERO_PLAY_COUNT = "ZERO_PLAY_COUNT"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
MISSING_RELEASE_DATE = "MISSING_RELEASE_DATE"
DATA_QUALITY_ERROR = "DATA_QUALITY_ERROR"


@dataclass(frozen=True, slots=True)
class ScoreCalculationResult:
    """Summary returned after one atomic score replacement."""

    score_date: date
    analysis_as_of: datetime
    algorithm_version: str
    score_scope_type: str
    score_scope_id: int
    calculated_count: int
    skipped_count: int
    skipped_reasons: dict[str, int]


@dataclass(frozen=True, slots=True)
class _EligibleCandidate:
    metric: MetricResult
    heat_score: Decimal
    growth_rate: float
    engagement_rate: float
    release_date: date


class ScoreService(BaseService):
    """Coordinate analytics, pure scoring, persistence, and one audit event."""

    def __init__(
        self,
        session: Session,
        analytics: AnalyticsService,
        scores: ScoreRepository,
        dramas: DramaRepository,
        operation_logs: OperationLogRepository,
    ) -> None:
        super().__init__(session, scores, dramas, operation_logs)
        self.analytics = analytics
        self.scores = scores
        self.dramas = dramas
        self.operation_logs = operation_logs

    def calculate_scores(
        self,
        score_date: date,
        *,
        administrator_id: int,
        now: datetime | None = None,
        request_id: str | None = None,
    ) -> ScoreCalculationResult:
        """Replace the fixed ALL-scope score set and audit it atomically."""

        analysis_as_of = _resolve_analysis_as_of(score_date, now=now)
        context = AnalysisContext(
            analysis_as_of=analysis_as_of,
            time_window=SCORE_TIME_WINDOW,
            granularity=SCORE_GRANULARITY,
        )

        # 评分结果与整批操作日志共享一个事务，任何一步失败都不能单独落库。
        with self.transaction():
            metrics, heat_scores, _ = self.analytics.get_rankings(context)
            skipped_reasons: Counter[str] = Counter()
            eligible: list[_EligibleCandidate] = []

            # 资格检查只消费 AnalyticsService 已计算的指标，不重复查询快照或复制算法。
            for metric in metrics:
                reason = self._eligibility_reason(metric, heat_scores)
                if reason is not None:
                    skipped_reasons[reason] += 1
                    continue

                release_date = self._get_release_date(metric.drama_id)
                if release_date is None:
                    skipped_reasons[MISSING_RELEASE_DATE] += 1
                    continue
                if release_date > score_date:
                    skipped_reasons[DATA_QUALITY_ERROR] += 1
                    continue

                heat = heat_scores[metric.object_key]
                eligible.append(
                    _EligibleCandidate(
                        metric=metric,
                        heat_score=round_half_up(heat.score),
                        growth_rate=float(metric.growth_7d),
                        engagement_rate=float(metric.engagement.engagement_rate),
                        release_date=release_date,
                    )
                )

            score_values = self._calculate_score_values(
                eligible,
                score_date=score_date,
                analysis_as_of=analysis_as_of,
                skipped_reasons=skipped_reasons,
            )
            self.scores.replace_scope_scores(
                score_date=score_date,
                algorithm_version=COMPOSITE_SCORE_VERSION,
                score_scope_type=SCORE_SCOPE_TYPE,
                score_scope_id=SCORE_SCOPE_ID,
                scores=score_values,
            )
            self._audit_calculation(
                administrator_id=administrator_id,
                request_id=request_id,
                score_date=score_date,
                success_count=len(score_values),
                skipped_reasons=skipped_reasons,
            )

        return ScoreCalculationResult(
            score_date=score_date,
            analysis_as_of=analysis_as_of,
            algorithm_version=COMPOSITE_SCORE_VERSION,
            score_scope_type=SCORE_SCOPE_TYPE,
            score_scope_id=SCORE_SCOPE_ID,
            calculated_count=len(score_values),
            skipped_count=sum(skipped_reasons.values()),
            skipped_reasons=dict(sorted(skipped_reasons.items())),
        )

    def get_ranking(
        self,
        score_date: date,
        *,
        page: int,
        page_size: int,
        level: str | None = None,
    ) -> Page[Any]:
        """Delegate fixed-scope ranking pagination to ScoreRepository."""

        return self.read(
            self.scores.paginate_ranking,
            score_date=score_date,
            algorithm_version=COMPOSITE_SCORE_VERSION,
            score_scope_type=SCORE_SCOPE_TYPE,
            score_scope_id=SCORE_SCOPE_ID,
            page=page,
            page_size=page_size,
            level=level,
        )

    def get_drama_score(self, drama_id: int) -> Any | None:
        """Delegate latest score lookup without recalculation."""

        return self.read(
            self.scores.get_latest_by_drama,
            drama_id=drama_id,
            algorithm_version=COMPOSITE_SCORE_VERSION,
            score_scope_type=SCORE_SCOPE_TYPE,
            score_scope_id=SCORE_SCOPE_ID,
        )

    def get_level_distribution(self, score_date: date) -> dict[str, int]:
        """Delegate persisted level aggregation without deriving levels."""

        return self.read(
            self.scores.get_level_distribution,
            score_date=score_date,
            algorithm_version=COMPOSITE_SCORE_VERSION,
            score_scope_type=SCORE_SCOPE_TYPE,
            score_scope_id=SCORE_SCOPE_ID,
        )

    def _eligibility_reason(
        self,
        metric: MetricResult,
        heat_scores: dict[int, Any],
    ) -> str | None:
        if metric.snapshot_time is None:
            return NO_VALID_SNAPSHOT
        if metric.quality_status == "ERROR" or metric.excluded_error_count > 0:
            return DATA_QUALITY_ERROR
        if not metric.raw.heat_complete:
            return INCOMPLETE_METRICS
        raw_values = (
            metric.raw.play_count,
            metric.raw.like_count,
            metric.raw.comment_count,
            metric.raw.favorite_count,
            metric.raw.share_count,
        )
        if any(value is not None and value < 0 for value in raw_values):
            return DATA_QUALITY_ERROR
        if metric.raw.play_count == 0:
            return ZERO_PLAY_COUNT
        if metric.insufficient_history or metric.growth_7d is None:
            return INSUFFICIENT_HISTORY
        if metric.engagement.engagement_rate is None:
            return INCOMPLETE_METRICS
        if metric.object_key not in heat_scores:
            return INCOMPLETE_METRICS
        if not isfinite(float(metric.growth_7d)):
            return DATA_QUALITY_ERROR
        if (
            not isfinite(float(metric.engagement.engagement_rate))
            or metric.engagement.engagement_rate < 0
        ):
            return DATA_QUALITY_ERROR
        heat_score = heat_scores[metric.object_key].score
        if not isfinite(float(heat_score)) or not 0 <= heat_score <= 100:
            return DATA_QUALITY_ERROR
        return None

    def _get_release_date(self, drama_id: int) -> date | None:
        drama = self.dramas.get_by_id(drama_id)
        if drama is None:
            return None
        if drama.premiere_date is not None:
            return drama.premiere_date
        online_dates = [
            relation.online_at.date()
            for relation in drama.platform_relations
            if relation.online_at is not None
        ]
        return min(online_dates, default=None)

    def _calculate_score_values(
        self,
        candidates: list[_EligibleCandidate],
        *,
        score_date: date,
        analysis_as_of: datetime,
        skipped_reasons: Counter[str],
    ) -> list[dict[str, Any]]:
        if not candidates:
            return []
        growth_rates = [candidate.growth_rate for candidate in candidates]
        engagement_rates = [candidate.engagement_rate for candidate in candidates]
        growth_min, growth_max = min(growth_rates), max(growth_rates)
        engagement_min, engagement_max = min(engagement_rates), max(engagement_rates)
        values: list[dict[str, Any]] = []

        for candidate in candidates:
            try:
                growth_score = calculate_growth_score(
                    candidate.growth_rate,
                    growth_min,
                    growth_max,
                )
                engagement_score = calculate_min_max_score(
                    candidate.engagement_rate,
                    engagement_min,
                    engagement_max,
                )
                lifecycle_score = calculate_lifecycle_stage_score(
                    candidate.release_date,
                    score_date,
                )
                result = calculate_composite_score(
                    heat_score=candidate.heat_score,
                    growth_score=growth_score,
                    engagement_score=engagement_score,
                    lifecycle_score=lifecycle_score,
                )
            except CompositeScoreValidationError:
                skipped_reasons[DATA_QUALITY_ERROR] += 1
                continue

            values.append(
                {
                    "drama_id": candidate.metric.drama_id,
                    "analysis_as_of": analysis_as_of,
                    "heat_score": candidate.heat_score,
                    "growth_score": growth_score,
                    "engagement_score": engagement_score,
                    "lifecycle_score": lifecycle_score,
                    "total_score": result.total_score,
                    "level": result.level,
                }
            )
        return values

    def _audit_calculation(
        self,
        *,
        administrator_id: int,
        request_id: str | None,
        score_date: date,
        success_count: int,
        skipped_reasons: Counter[str],
    ) -> None:
        detail = {
            "score_date": score_date.isoformat(),
            "algorithm_version": COMPOSITE_SCORE_VERSION,
            "scope": {"type": SCORE_SCOPE_TYPE, "id": SCORE_SCOPE_ID},
            "success_count": success_count,
            "failed_count": sum(skipped_reasons.values()),
            "skipped_reasons": dict(sorted(skipped_reasons.items())),
        }
        values: dict[str, Any] = {
            "actor_user_id": administrator_id,
            "target_user_id": administrator_id,
            "operation_type": "SCORE_CALCULATE",
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


def _resolve_analysis_as_of(
    score_date: date,
    *,
    now: datetime | None = None,
) -> datetime:
    current = now or datetime.now(BUSINESS_TIME_ZONE)
    if current.tzinfo is None:
        current = current.replace(tzinfo=BUSINESS_TIME_ZONE)
    else:
        current = current.astimezone(BUSINESS_TIME_ZONE)
    if score_date > current.date():
        raise ValidationException(
            "Score date cannot be in the future",
            details={"score_date": score_date.isoformat()},
        )
    local_cutoff = (
        current
        if score_date == current.date()
        else datetime.combine(score_date, time.max, tzinfo=BUSINESS_TIME_ZONE)
    )
    return local_cutoff.astimezone(UTC).replace(tzinfo=None)
