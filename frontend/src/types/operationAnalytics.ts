export type AvailabilityStatus = 'AVAILABLE' | 'PARTIAL' | 'INSUFFICIENT' | 'NOT_AVAILABLE'

export type AvailabilityReason =
  | 'NOT_CALCULATED'
  | 'INSUFFICIENT_HISTORY'
  | 'INCOMPLETE_BEFORE_WINDOW'
  | 'INCOMPLETE_AFTER_WINDOW'
  | 'INCOMPARABLE_SCOPE'
  | 'MISSING_METRIC'
  | 'ZERO_BASELINE'
  | 'OVERLAPPING_ACTIONS'
  | 'MIXED_SOURCE_VERSIONS'
  | 'INVALID_CUMULATIVE_SEQUENCE'
  | 'NOT_COMPLETED'
  | 'GLOBAL_ACTION_UNSUPPORTED'
  | 'NOT_AVAILABLE'

export interface AnalysisAvailability {
  status: AvailabilityStatus
  reasons: AvailabilityReason[]
}

export interface AnalysisWindow {
  start_date: string
  end_date: string
  day_count: number
}

export type NumericValue = number | string

export interface MetricChange {
  metric_type: string
  before_value: NumericValue | null
  after_value: NumericValue | null
  absolute_change: NumericValue | null
  relative_change: string | null
  direction: string
  unit: string
  availability: AnalysisAvailability
}

export interface OperationEffectivenessResult {
  action_id: number
  drama_id: number
  before_window: AnalysisWindow
  after_window: AnalysisWindow
  metric_changes: MetricChange[]
  availability: AnalysisAvailability
  anchor_time: string
  overlapping_action_ids: number[]
  action_effect_rule_version: string
  analysis_revision: string | null
  analysis_as_of: string | null
  disclaimer: string
}

export interface OperationEffectivenessPage {
  page: number
  page_size: number
  total: number
  items: OperationEffectivenessResult[]
  availability: AnalysisAvailability
  analysis_as_of: string
}

export interface LifecycleEvidence {
  previous_window: AnalysisWindow
  current_window: AnalysisWindow
  previous_average: string | null
  current_average: string | null
  window_change_rate: string | null
}

export type LifecycleStage = 'LAUNCH' | 'GROWTH' | 'STABLE' | 'DECLINE' | 'ARCHIVED'

export interface LifecycleResult {
  drama_id: number
  lifecycle_stage: LifecycleStage | null
  rule_version: string
  evaluated_as_of: string
  availability: AnalysisAvailability
  evidence: LifecycleEvidence | null
  analysis_revision: string | null
}

export interface ComparisonScope {
  drama_ids: number[]
  platform_id: number
}

export interface BenchmarkMetric {
  metric_type: string
  value: NumericValue | null
  group_median: string | null
  unit: string
  availability: AnalysisAvailability
}

export interface BenchmarkMember {
  drama_id: number
  metrics: BenchmarkMetric[]
  availability: AnalysisAvailability
}

export interface BenchmarkResult {
  target_drama_id: number | null
  comparison_scope: ComparisonScope
  window: AnalysisWindow
  metrics: BenchmarkMember[]
  availability: AnalysisAvailability
  benchmark_version: string
  lifecycle_rule_version: string
  analysis_revision: string | null
  analysis_as_of: string
}

export interface OperationEffectivenessQuery {
  action_id?: number
  drama_id?: number
  analysis_as_of?: string
  page?: number
  page_size?: number
}

export interface BenchmarkQuery {
  drama_ids: number[]
  platform_id: number
  analysis_as_of?: string
}
