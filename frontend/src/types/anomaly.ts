import type { Pagination } from './api'

export type AnomalySeverity = 'A' | 'B' | 'C'
export type AnomalyStatus = 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED' | 'IGNORED'
export type AnomalyType =
  | 'PLAY_COUNT_GROWTH_ANOMALY'
  | 'PLAY_COUNT_DROP_ANOMALY'
  | 'ENGAGEMENT_RATE_ANOMALY'
  | 'DATA_SPIKE_ANOMALY'
export type MetricType = 'PLAY_COUNT' | 'ENGAGEMENT_RATE'

export interface AnomalyRecord {
  record_id: number
  drama_id: number
  drama_code: string
  drama_name: string
  metric_type: MetricType
  anomaly_type: AnomalyType
  severity: AnomalySeverity
  status: AnomalyStatus
  analysis_as_of: string
  algorithm_version: string
  evidence_summary: string
  created_at: string
  updated_at: string
}

export interface AnomalyDetectionResult {
  analysis_as_of: string
  algorithm_version: string
  detected_count: number
  skipped_count: number
  skip_reasons: Record<string, number>
}

export interface AnomalyStatistics {
  total_count: number
  severity_distribution: Record<AnomalySeverity, number>
  status_distribution: Record<AnomalyStatus, number>
  type_distribution: Record<string, number>
}

export interface AnomalyQuery {
  analysis_as_of?: string
  metric_type?: MetricType
  anomaly_type?: AnomalyType
  severity?: AnomalySeverity
  status?: AnomalyStatus
  page?: number
  page_size?: number
}

export type AnomalyPage = Pagination<AnomalyRecord>
