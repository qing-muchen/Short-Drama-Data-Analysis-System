import apiClient from './axios'
import type { ApiResponse, Pagination } from '../types/api'
import type {
  Explanation,
  ExplanationEntityType,
  ExplanationModuleType,
  LineagePage,
  LineageRecord,
  LineageRelationshipType,
  LineageSourceType,
  LineageTargetType,
} from '../types/explanation'

export interface ExplanationQuery {
  module_type?: ExplanationModuleType
  analysis_as_of?: string
  algorithm_version?: string
  rule_set_version?: string
  page?: number
  page_size?: number
}

export interface LineageQuery {
  source_type?: LineageSourceType
  relationship_type?: LineageRelationshipType
  page?: number
  page_size?: number
}

export async function getExplanations(
  entityType: ExplanationEntityType,
  entityId: number,
  params: ExplanationQuery = {},
): Promise<Pagination<Explanation>> {
  const response = await apiClient.get<ApiResponse<Pagination<Explanation>>>(
    `/explanations/${entityType}/${entityId}`,
    { params },
  )
  return response.data.data
}
export async function getLineage(
  targetType: LineageTargetType,
  targetId: number,
  params: LineageQuery = {},
): Promise<LineagePage> {
  const response = await apiClient.get<ApiResponse<LineagePage>>(
    `/lineage/${targetType}/${targetId}`,
    { params },
  )
  return response.data.data
}
