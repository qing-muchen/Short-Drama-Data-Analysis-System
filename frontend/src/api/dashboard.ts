import apiClient from './axios'
import type { ApiResponse } from '../types/api'
import type {
  DashboardOverview,
  QualitySummary,
  RankingItem,
  TrendItem,
} from '../types/dashboard'

export async function getOverview(): Promise<DashboardOverview> {
  const response = await apiClient.get<ApiResponse<DashboardOverview>>('/dashboard/overview')
  return response.data.data
}

export async function getHeatRanking(): Promise<RankingItem[]> {
  const response = await apiClient.get<ApiResponse<RankingItem[]>>('/dashboard/rankings/heat', {
    params: { limit: 10 },
  })
  return response.data.data
}

export async function getGrowthRanking(): Promise<RankingItem[]> {
  const response = await apiClient.get<ApiResponse<RankingItem[]>>('/dashboard/rankings/growth', {
    params: { limit: 10 },
  })
  return response.data.data
}

export async function getPotentialRanking(): Promise<RankingItem[]> {
  const response = await apiClient.get<ApiResponse<RankingItem[]>>(
    '/dashboard/rankings/potential',
    { params: { limit: 10 } },
  )
  return response.data.data
}

export async function getTrend(): Promise<TrendItem[]> {
  const response = await apiClient.get<ApiResponse<TrendItem[]>>('/dashboard/trend')
  return response.data.data
}

export async function getQuality(): Promise<QualitySummary> {
  const response = await apiClient.get<ApiResponse<QualitySummary>>('/dashboard/quality')
  return response.data.data
}
