export type QualityGrade = 'S' | 'A' | 'B' | 'C'
export type QualityScopeType = 'ALL'
export type QualityDimension =
  | 'COMPLETENESS'
  | 'ACCURACY'
  | 'CONSISTENCY'
  | 'TIMELINESS'
export type QualityRuleStatus = 'DRAFT' | 'ACTIVE' | 'INACTIVE'
export type QualityResultStatus = 'APPLIED' | 'NOT_APPLICABLE'
export type QualityScoringMethod = 'PASS_RATE' | 'BUCKET_AVERAGE'
export type QualitySeverity = 'INFO' | 'WARNING' | 'ERROR'
export type QualityTargetEntityType =
  | 'DRAMA'
  | 'DRAMA_PLATFORM'
  | 'SNAPSHOT'
  | 'IMPORT_JOB'

export interface DataQualityCalculationResult {
  quality_score_id: number
  score_date: string
  analysis_as_of: string
  algorithm_version: 'Quality Score V1.0'
  rule_set_version: 'DQ Rules 1.0'
  rule_set_hash: string
  score_scope_type: QualityScopeType
  score_scope_id: 0
  rule_count: number
  applied_rule_count: number
  not_applicable_rule_count: number
  evaluated_entity_count: number
  total_score: number
  quality_grade: QualityGrade
}

export interface DataQualityRuleResult {
  quality_rule_result_id: number
  quality_rule_id: number
  rule_code: string
  rule_version: string
  rule_name: string
  dimension: QualityDimension
  result_status: QualityResultStatus
  applicable_count: number
  passed_count: number
  failed_count: number
  rule_score: number | null
  not_applicable_reason: string | null
  evidence_summary: string | null
  created_at: string
}

export interface DataQualityScore {
  quality_score_id: number
  score_date: string
  score_scope_type: QualityScopeType
  score_scope_id: 0
  analysis_as_of: string
  completeness_score: number
  accuracy_score: number
  consistency_score: number
  timeliness_score: number
  total_score: number
  quality_grade: QualityGrade
  algorithm_version: 'Quality Score V1.0'
  rule_set_version: 'DQ Rules 1.0'
  rule_set_hash: string
  evaluated_entity_count: number
  open_issue_count: number
  source_watermark: Record<string, unknown> | null
  created_at: string
  updated_at: string
  rule_results: DataQualityRuleResult[]
}

export interface DataQualityHistoryItem {
  quality_score_id: number
  score_date: string
  analysis_as_of: string
  completeness_score: number
  accuracy_score: number
  consistency_score: number
  timeliness_score: number
  total_score: number
  quality_grade: QualityGrade
  algorithm_version: 'Quality Score V1.0'
  rule_set_version: 'DQ Rules 1.0'
  rule_set_hash: string
  score_scope_type: QualityScopeType
  score_scope_id: 0
  evaluated_entity_count: number
  open_issue_count: number
}

export interface DataQualityHistory {
  total: number
  items: DataQualityHistoryItem[]
}

export interface DataQualityRule {
  quality_rule_id: number
  rule_code: string
  rule_version: string
  rule_name: string
  dimension: QualityDimension
  target_entity_type: QualityTargetEntityType
  evaluator_key: string
  scoring_method: QualityScoringMethod
  weight: number
  severity: QualitySeverity
  configuration: Record<string, unknown>
  status: QualityRuleStatus
  valid_from: string
  valid_to: string | null
  description: string | null
}

export interface DataQualityRuleList {
  rule_set_version: 'DQ Rules 1.0'
  rule_set_hash: string | null
  total: number
  items: DataQualityRule[]
}

export interface DataQualityHistoryParams {
  start_date?: string
  end_date?: string
  limit?: number
}
