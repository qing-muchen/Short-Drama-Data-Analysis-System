import axios from 'axios'

import apiClient from './axios'
import type { ApiResponse } from '../types/api'
import type {
  DataQualityCalculationResult,
  DataQualityHistory,
  DataQualityHistoryParams,
  DataQualityRuleList,
  DataQualityScore,
  QualityAlgorithmVersion,
} from '../types/dataQuality'

const DATA_QUALITY_REQUEST_TIMEOUT_MS = 60_000

export async function calculateDataQuality(
  scoreDate: string,
  algorithmVersion: QualityAlgorithmVersion,
): Promise<DataQualityCalculationResult> {
  const response = await apiClient.post<ApiResponse<DataQualityCalculationResult>>(
    '/data-quality/calculate',
    { score_date: scoreDate, algorithm_version: algorithmVersion },
    { timeout: DATA_QUALITY_REQUEST_TIMEOUT_MS },
  )
  return response.data.data
}

export async function getCurrentDataQualityScore(
  algorithmVersion: QualityAlgorithmVersion,
): Promise<DataQualityScore | null> {
  try {
    const response = await apiClient.get<ApiResponse<DataQualityScore>>(
      '/data-quality/score',
      {
        params: { algorithm_version: algorithmVersion },
        timeout: DATA_QUALITY_REQUEST_TIMEOUT_MS,
      },
    )
    return response.data.data
  } catch (error: unknown) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return null
    }
    throw error
  }
}

export async function getDataQualityHistory(
  params: DataQualityHistoryParams = {},
): Promise<DataQualityHistory> {
  const response = await apiClient.get<ApiResponse<DataQualityHistory>>(
    '/data-quality/history',
    {
      params,
      timeout: DATA_QUALITY_REQUEST_TIMEOUT_MS,
    },
  )
  return response.data.data
}

export async function getDataQualityRules(
  algorithmVersion: QualityAlgorithmVersion,
): Promise<DataQualityRuleList> {
  const response = await apiClient.get<ApiResponse<DataQualityRuleList>>(
    '/data-quality/rules',
    {
      params: { algorithm_version: algorithmVersion },
      timeout: DATA_QUALITY_REQUEST_TIMEOUT_MS,
    },
  )
  return response.data.data
}
