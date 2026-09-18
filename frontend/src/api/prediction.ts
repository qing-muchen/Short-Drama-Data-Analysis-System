import axios from 'axios'

import apiClient from './axios'
import type { ApiResponse } from '../types/api'
import type {
  Prediction,
  PredictionCalculateResponse,
  PredictionHistoryResponse,
} from '../types/prediction'

const PREDICTION_REQUEST_TIMEOUT_MS = 60_000

export async function getPrediction(dramaId: number): Promise<Prediction | null> {
  try {
    const response = await apiClient.get<ApiResponse<Prediction>>(`/predictions/${dramaId}`, {
      timeout: PREDICTION_REQUEST_TIMEOUT_MS,
    })
    return response.data.data
  } catch (error: unknown) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return null
    }
    throw error
  }
}

export async function getPredictionHistory(
  dramaId: number,
  limit = 100,
): Promise<PredictionHistoryResponse> {
  const response = await apiClient.get<ApiResponse<PredictionHistoryResponse>>(
    `/predictions/${dramaId}/history`,
    {
      params: { limit },
      timeout: PREDICTION_REQUEST_TIMEOUT_MS,
    },
  )
  return response.data.data
}

export async function calculatePrediction(
  dramaId: number,
  analysisAsOf?: string,
): Promise<PredictionCalculateResponse> {
  const payload: { drama_id: number; analysis_as_of?: string } = { drama_id: dramaId }
  if (analysisAsOf) {
    payload.analysis_as_of = analysisAsOf
  }
  const response = await apiClient.post<ApiResponse<PredictionCalculateResponse>>(
    '/predictions/calculate',
    payload,
    { timeout: PREDICTION_REQUEST_TIMEOUT_MS },
  )
  return response.data.data
}
