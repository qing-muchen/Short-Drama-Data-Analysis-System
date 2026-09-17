import axios from 'axios'

import apiClient from './axios'
import type { ApiResponse } from '../types/api'
import type {
  DataQualityCalculationResult,
  DataQualityHistory,
  DataQualityHistoryParams,
  DataQualityRuleList,
  DataQualityScore,
} from '../types/dataQuality'

const DATA_QUALITY_REQUEST_TIMEOUT_MS = 60_000

export async function calculateDataQuality(
  scoreDate: string,
): Promise<DataQualityCalculationResult> {
  const response = await apiClient.post<ApiResponse<DataQualityCalculationResult>>(
    '/data-quality/calculate',
    { score_date: scoreDate },
    { timeout: DATA_QUALITY_REQUEST_TIMEOUT_MS },
  )
  return response.data.data
}

export async function getCurrentDataQualityScore(): Promise<DataQualityScore | null> {
  try {
    const response = await apiClient.get<ApiResponse<DataQualityScore>>(
      '/data-quality/score',
      { timeout: DATA_QUALITY_REQUEST_TIMEOUT_MS },
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

export async function getDataQualityRules(): Promise<DataQualityRuleList> {
  const response = await apiClient.get<ApiResponse<DataQualityRuleList>>(
    '/data-quality/rules',
    { timeout: DATA_QUALITY_REQUEST_TIMEOUT_MS },
  )
  return response.data.data
}
