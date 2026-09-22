import type { Pagination } from './api'

export type ExplanationEntityType = 'SCORE' | 'QUALITY' | 'PREDICTION' | 'ANOMALY' | 'ACTION'
export type ExplanationModuleType =
  | 'SCORE'
  | 'QUALITY'
  | 'PREDICTION'
  | 'ANOMALY'
  | 'OPERATION_ACTION'
export type LineageTargetType =
  | 'EXPLANATION'
  | 'SCORE'
  | 'QUALITY'
  | 'PREDICTION'
  | 'ANOMALY'
  | 'ACTION'
export type LineageSourceType = 'METRIC' | 'SNAPSHOT' | 'RULE' | 'PREDICTION_INPUT' | 'ANOMALY_EVIDENCE'
export type LineageRelationshipType = 'DERIVED_FROM' | 'USES_METRIC' | 'USES_RULE' | 'USES_WINDOW'

export interface ExplanationDetail {
  reason: string
  inputs: unknown[]
  rules: unknown[]
  versions: Record<string, unknown>
  evidence: unknown[]
  [key: string]: unknown
}

export interface Explanation {
  explanation_id: number
  entity_type: ExplanationEntityType
  entity_id: number
  module_type: ExplanationModuleType
  summary: string
  detail: ExplanationDetail
  algorithm_version: string
  rule_set_version: string
  analysis_as_of: string
  created_at: string
}

export interface LineageRecord {
  lineage_id: number
  target_type: LineageTargetType
  target_id: number
  source_type: LineageSourceType
  source_id: number
  relationship_type: LineageRelationshipType
  analysis_as_of: string
  created_at: string
}

export type ExplanationPage = Pagination<Explanation>
export type LineagePage = Pagination<LineageRecord>
