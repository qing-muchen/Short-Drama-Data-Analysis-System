import apiClient from './axios'
import type { ApiResponse } from '../types/api'
import type {
  AnomalyDetectionResult,
  AnomalyPage,
  AnomalyQuery,
  AnomalyRecord,
  AnomalyStatistics,
  AnomalyStatus,
} from '../types/anomaly'

const ANOMALY_REQUEST_TIMEOUT_MS = 60_000

export async function detectAnomalies(analysisAsOf?: string): Promise<AnomalyDetectionResult> {
  const response = await apiClient.post<ApiResponse<AnomalyDetectionResult>>(
    '/anomalies/detect',
    analysisAsOf ? { analysis_as_of: analysisAsOf } : {},
    { timeout: ANOMALY_REQUEST_TIMEOUT_MS },
  )
  return response.data.data
}

export async function getAnomalies(params: AnomalyQuery = {}): Promise<AnomalyPage> {
  const response = await apiClient.get<ApiResponse<AnomalyPage>>('/anomalies', {
    params,
    timeout: ANOMALY_REQUEST_TIMEOUT_MS,
  })
  return response.data.data
}

export async function getDramaAnomalies(dramaId: number): Promise<AnomalyRecord[]> {
  const response = await apiClient.get<ApiResponse<AnomalyRecord[]>>(`/anomalies/${dramaId}`, {
    timeout: ANOMALY_REQUEST_TIMEOUT_MS,
  })
  return response.data.data
}

export async function getAnomalyStatistics(): Promise<AnomalyStatistics> {
  const response = await apiClient.get<ApiResponse<AnomalyStatistics>>('/anomalies/statistics', {
    timeout: ANOMALY_REQUEST_TIMEOUT_MS,
  })
  return response.data.data
}

export async function updateAnomalyStatus(
  recordId: number,
  status: AnomalyStatus,
): Promise<AnomalyRecord> {
  const response = await apiClient.patch<ApiResponse<AnomalyRecord>>(
    `/anomalies/${recordId}/status`,
    { status },
    { timeout: ANOMALY_REQUEST_TIMEOUT_MS },
  )
  return response.data.data
}
