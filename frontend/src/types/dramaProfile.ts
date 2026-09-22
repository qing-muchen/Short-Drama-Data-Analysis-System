export type AvailabilityReason =
  | 'NOT_CALCULATED'
  | 'INSUFFICIENT_HISTORY'
  | 'NO_ANOMALY'
  | 'NOT_DETECTED'
  | 'NOT_AVAILABLE'

export interface ModuleAvailability {
  available: boolean
  reason?: AvailabilityReason | null
}

export interface DramaProfileBasic {
  drama_id: number
  title: string
  platform: string | null
  tags: string[]
}

export interface ScoreProfileSummary {
  available: ModuleAvailability
  score_level: string | null
  dimensions: Record<string, number>
  analysis_as_of: string | null
  algorithm_version: string | null
  rule_set_version: string | null
}

export interface QualityProfileSummary {
  available: ModuleAvailability
  quality_level: string | null
  quality_status: string | null
  risk_message: string | null
  analysis_as_of: string | null
  rule_set_version: string | null
}

export interface PredictionProfileSummary {
  available: ModuleAvailability
  trend_direction: string | null
  prediction_status: string | null
  analysis_as_of: string | null
  algorithm_version: string | null
}

export interface AnomalySummaryItem {
  anomaly_id?: number
  anomaly_type?: string
  severity?: string
  status?: string
  analysis_as_of?: string
}

export interface AnomalyProfileSummary {
  available: ModuleAvailability
  active_count: number
  highest_severity: string | null
  latest_anomalies: AnomalySummaryItem[]
  analysis_as_of: string | null
}

export interface ActionSummaryItem {
  action_id?: number
  title?: string
  status?: string
  priority?: string
  updated_at?: string
}

export interface ActionProfileSummary {
  available: ModuleAvailability
  open_count: number
  in_progress_count: number
  recent_actions: ActionSummaryItem[]
}

export interface ExplanationProfileSummary {
  available: ModuleAvailability
  latest_explanation: Record<string, unknown> | null
  lineage_available: boolean
}

export interface DramaProfileResponse {
  drama: DramaProfileBasic
  availability: Record<string, ModuleAvailability>
  performance: ScoreProfileSummary | null
  quality: QualityProfileSummary | null
  trend: PredictionProfileSummary | null
  risk: AnomalyProfileSummary | null
  operations: ActionProfileSummary | null
  explanations: ExplanationProfileSummary | null
}
