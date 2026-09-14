import type { Pagination } from './api'

export type ScoreLevel = 'S' | 'A' | 'B' | 'C'
export type ScoreScopeType = 'ALL'
export type ScoreSkipReason =
  | 'NO_VALID_SNAPSHOT'
  | 'INCOMPLETE_METRICS'
  | 'ZERO_PLAY_COUNT'
  | 'INSUFFICIENT_HISTORY'
  | 'MISSING_RELEASE_DATE'
  | 'DATA_QUALITY_ERROR'

export interface ScoreCalculationResult {
  score_date: string
  analysis_as_of: string
  algorithm_version: 'Composite Score V1.0'
  score_scope_type: ScoreScopeType
  score_scope_id: 0
  calculated_count: number
  skipped_count: number
  skipped_reasons: Partial<Record<ScoreSkipReason, number>>
}

export interface DramaScore {
  score_id: number
  drama_id: number
  drama_code: string
  drama_name: string
  score_date: string
  score_scope_type: ScoreScopeType
  score_scope_id: 0
  analysis_as_of: string
  heat_score: number
  growth_score: number
  engagement_score: number
  lifecycle_score: number
  total_score: number
  level: ScoreLevel
  algorithm_version: 'Composite Score V1.0'
  created_at: string
  updated_at: string
}

export interface ScoreRankingItem extends DramaScore {
  rank: number
}

export interface ScoreLevelCount {
  level: ScoreLevel
  count: number
}

export interface ScoreLevelDistribution {
  score_date: string
  algorithm_version: 'Composite Score V1.0'
  score_scope_type: ScoreScopeType
  score_scope_id: 0
  total: number
  items: ScoreLevelCount[]
}

export type ScoreRankingPage = Pagination<ScoreRankingItem>
