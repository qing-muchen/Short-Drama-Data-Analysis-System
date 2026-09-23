import apiClient from './axios'
import type { ApiResponse } from '../types/api'
import type {
  BenchmarkQuery,
  BenchmarkResult,
  LifecycleResult,
  OperationEffectivenessPage,
  OperationEffectivenessQuery,
} from '../types/operationAnalytics'

export async function getOperationEffectiveness(
  params: OperationEffectivenessQuery = {},
): Promise<OperationEffectivenessPage> {
  const response = await apiClient.get<ApiResponse<OperationEffectivenessPage>>(
    '/operations/effectiveness',
    { params },
  )
  return response.data.data
}

export async function getDramaLifecycle(
  dramaId: number,
  analysisAsOf?: string,
): Promise<LifecycleResult> {
  const response = await apiClient.get<ApiResponse<LifecycleResult>>(
    `/dramas/${dramaId}/lifecycle`,
    { params: analysisAsOf ? { analysis_as_of: analysisAsOf } : undefined },
  )
  return response.data.data
}

export async function getDramaBenchmark(params: BenchmarkQuery): Promise<BenchmarkResult> {
  const search = new URLSearchParams()
  params.drama_ids.forEach((dramaId) => search.append('drama_ids', String(dramaId)))
  search.set('platform_id', String(params.platform_id))
  if (params.analysis_as_of) search.set('analysis_as_of', params.analysis_as_of)

  const response = await apiClient.get<ApiResponse<BenchmarkResult>>('/dramas/benchmark', {
    params: search,
  })
  return response.data.data
}
