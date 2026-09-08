export interface DashboardOverview {
  analysis_as_of: string
  drama_count: number
  actor_count: number
  director_count: number
  company_count: number
  platform_count: number
  tag_count: number
  total_play_count: number
  average_engagement_rate: number | null
  quality_issue_count: number
}

export interface RankingItem {
  drama_id: number
  drama_name: string
  platform_count: number
  heat_score: number | null
  growth_rate: number | null
  current_play_count: number | null
  potential_score: number | null
  growth_7d: number | null
}

export interface TrendItem {
  date: string
  play_count: number | null
  engagement_rate: number | null
}

export interface FreshnessSummary {
  fresh: number
  stale: number
  unknown?: number
}

export interface QualitySummary {
  analysis_as_of: string
  quality_issue_count: number
  warning_count: number
  error_count: number
  freshness_summary: FreshnessSummary
}
