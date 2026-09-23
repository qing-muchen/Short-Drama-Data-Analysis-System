import apiClient from './axios'
import type { ApiResponse } from '../types/api'
import type {
  CompletenessResult,
  ConsistencyResult,
  DataGovernanceDetailQuery,
  DataGovernanceQuery,
  DataGovernanceResponse,
  FreshnessResult,
} from '../types/dataGovernance'

export async function getDataGovernanceOverview(
  params: DataGovernanceQuery = {},
): Promise<DataGovernanceResponse> {
  const response = await apiClient.get<ApiResponse<DataGovernanceResponse>>(
    '/data-quality/overview',
    { params },
  )
  return response.data.data
}

export async function getFreshnessQuality(
  params: DataGovernanceDetailQuery = {},
): Promise<FreshnessResult> {
  const response = await apiClient.get<ApiResponse<FreshnessResult>>(
    '/data-quality/freshness',
    { params },
  )
  return response.data.data
}

export async function getCompletenessQuality(
  params: DataGovernanceDetailQuery = {},
): Promise<CompletenessResult> {
  const response = await apiClient.get<ApiResponse<CompletenessResult>>(
    '/data-quality/completeness',
    { params },
  )
  return response.data.data
}

export async function getConsistencyQuality(
  params: DataGovernanceDetailQuery = {},
): Promise<ConsistencyResult> {
  const response = await apiClient.get<ApiResponse<ConsistencyResult>>(
    '/data-quality/consistency',
    { params },
  )
  return response.data.data
}
