export type QualityStatus = 'HEALTHY' | 'WARNING' | 'FAILED' | 'NOT_AVAILABLE'

export type AvailabilityStatus = 'AVAILABLE' | 'PARTIAL' | 'INSUFFICIENT' | 'NOT_AVAILABLE'

export type AvailabilityReason =
  | 'NO_DATA'
  | 'MISSING_SOURCE'
  | 'INSUFFICIENT_HISTORY'
  | 'MISSING_REQUIRED_FIELD'
  | 'INCOMPLETE_TIME_SERIES'
  | 'UNRESOLVED_RELATION'
  | 'REVISION_NOT_VISIBLE'
  | 'UNSUPPORTED_SCOPE'
  | 'EVALUATION_FAILED'
  | 'NOT_AVAILABLE'

export type GovernanceScope = 'SYSTEM'

export type QualityIssueType = 'FRESHNESS' | 'COMPLETENESS' | 'CONSISTENCY'

export interface DataQualityAvailability {
  status: AvailabilityStatus
  reasons: AvailabilityReason[]
  message: string | null
}

export interface EvidenceItem {
  evidence_type: QualityIssueType
  message: string
  source: string
  metadata: Record<string, unknown>
}

export interface EvidencePage {
  evidence: EvidenceItem[]
  page: number
  page_size: number
  total: number
}

export interface FreshnessResult extends EvidencePage {
  status: QualityStatus
  availability: DataQualityAvailability
  delay_seconds: number | null
  rule_version: string
  analysis_as_of: string | null
  summary: string | null
}

export interface CompletenessResult extends EvidencePage {
  status: QualityStatus
  availability: DataQualityAvailability
  coverage_ratio: string | null
  missing_items: string[]
  rule_version: string
  analysis_as_of: string | null
  summary: string | null
}

export interface ConsistencyResult extends EvidencePage {
  status: QualityStatus
  availability: DataQualityAvailability
  issue_count: number
  rule_version: string
  analysis_as_of: string | null
  summary: string | null
}

export interface DataGovernanceResponse {
  scope: GovernanceScope
  analysis_as_of: string
  availability: DataQualityAvailability
  freshness: FreshnessResult
  completeness: CompletenessResult
  consistency: ConsistencyResult
  rule_set_version: string
}

export interface DataGovernanceQuery {
  analysis_as_of?: string
}

export interface DataGovernanceDetailQuery extends DataGovernanceQuery {
  page?: number
  page_size?: number
}
