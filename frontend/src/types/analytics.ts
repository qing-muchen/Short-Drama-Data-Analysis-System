export type AnalysisGranularity = 'DRAMA_PLATFORM' | 'DRAMA_OVERALL'
export type TimeWindow = '24H' | '7D' | '30D'
export type Freshness = 'FRESH' | 'STALE'
export type QualityStatus = 'NORMAL' | 'WARNING' | 'ERROR'
export type InsightType =
  | 'PERFORMANCE'
  | 'GROWTH'
  | 'POTENTIAL'
  | 'RISK'
  | 'PLATFORM'
  | 'TAG'
  | 'DATA_QUALITY'

export interface ModelVersions {
  heat: string
  potential: string
  anomaly: string
  insight: string
  metrics: string
}

export interface AnalysisContext {
  analysis_as_of: string
  time_window: TimeWindow
  granularity: AnalysisGranularity
  platform_scope: number[]
  tag_scope: number[]
  quality_policy: 'VALID_WITH_WARNINGS'
  model_versions: ModelVersions
}

export interface RawMetricSummary {
  play_count: number | null
  like_count: number | null
  comment_count: number | null
  favorite_count: number | null
  share_count: number | null
  ranking: number | null
}

export interface EngagementMetricSummary {
  like_rate: number | null
  comment_rate: number | null
  favorite_rate: number | null
  share_rate: number | null
  engagement_rate: number | null
  quality_engagement: number | null
}

export interface GrowthResult {
  adjacent_growth: number | null
  growth_24h: number | null
  growth_7d: number | null
  growth_30d: number | null
}

export interface MetricSummary extends GrowthResult {
  object_key: number
  drama_id: number
  drama_code: string
  granularity: AnalysisGranularity
  snapshot_time: string | null
  raw: RawMetricSummary
  engagement: EngagementMetricSummary
  freshness: Freshness | null
  quality_status: QualityStatus | null
  warning_count: number
  excluded_error_count: number
  insufficient_history: boolean
  included_platform_count: number
}

export interface HeatResult {
  object_key: number
  score: number
  rank: number
  candidate_count: number
  model_version: string
}

export interface PotentialResult {
  object_key: number
  score: number
  rank: number
  candidate_count: number
  model_version: string
}

export interface InsightItem {
  insight_type: InsightType
  rule_code: string
  trigger: string
  evidence: Record<string, unknown>
  conclusion: string
  priority: number
  rule_set_version: string
}

export interface DramaAnalysisSummary {
  context: AnalysisContext
  metrics: MetricSummary
  heat: HeatResult | null
  potential: PotentialResult | null
  insights: InsightItem[]
}
