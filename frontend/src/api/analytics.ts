import apiClient from './axios'
import type { ApiResponse } from '../types/api'
import type { DramaAnalysisSummary } from '../types/analytics'

export async function getDramaAnalysisSummary(dramaId: number): Promise<DramaAnalysisSummary> {
  const response = await apiClient.get<ApiResponse<DramaAnalysisSummary>>(
    `/analytics/dramas/${dramaId}/summary`,
  )
  return response.data.data
}
