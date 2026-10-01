import apiClient from './axios'
import type { ApiResponse } from '../types/api'
import type {
  DashboardOverview,
  QualitySummary,
  RankingItem,
  TagDistributionItem,
  TrendItem,
} from '../types/dashboard'

const DASHBOARD_REQUEST_TIMEOUT_MS = 60_000

export async function getOverview(analysisAsOf: string): Promise<DashboardOverview> {
  const response = await apiClient.get<ApiResponse<DashboardOverview>>('/dashboard/overview', {
    params: { analysis_as_of: analysisAsOf },
    timeout: DASHBOARD_REQUEST_TIMEOUT_MS,
  })
  return response.data.data
}

export async function getHeatRanking(analysisAsOf: string): Promise<RankingItem[]> {
  const response = await apiClient.get<ApiResponse<RankingItem[]>>('/dashboard/rankings/heat', {
    params: { limit: 10, analysis_as_of: analysisAsOf },
    timeout: DASHBOARD_REQUEST_TIMEOUT_MS,
  })
  return response.data.data
}

export async function getGrowthRanking(analysisAsOf: string): Promise<RankingItem[]> {
  const response = await apiClient.get<ApiResponse<RankingItem[]>>('/dashboard/rankings/growth', {
    params: { limit: 10, analysis_as_of: analysisAsOf },
    timeout: DASHBOARD_REQUEST_TIMEOUT_MS,
  })
  return response.data.data
}

export async function getPotentialRanking(analysisAsOf: string): Promise<RankingItem[]> {
  const response = await apiClient.get<ApiResponse<RankingItem[]>>(
    '/dashboard/rankings/potential',
    {
      params: { limit: 10, analysis_as_of: analysisAsOf },
      timeout: DASHBOARD_REQUEST_TIMEOUT_MS,
    },
  )
  return response.data.data
}

export async function getTrend(analysisAsOf: string): Promise<TrendItem[]> {
  const response = await apiClient.get<ApiResponse<TrendItem[]>>('/dashboard/trend', {
    params: { analysis_as_of: analysisAsOf },
    timeout: DASHBOARD_REQUEST_TIMEOUT_MS,
  })
  return response.data.data
}

export async function getQuality(analysisAsOf: string): Promise<QualitySummary> {
  const response = await apiClient.get<ApiResponse<QualitySummary>>('/dashboard/quality', {
    params: { analysis_as_of: analysisAsOf },
    timeout: DASHBOARD_REQUEST_TIMEOUT_MS,
  })
  return response.data.data
}

export async function getTagDistribution(): Promise<TagDistributionItem[]> {
  const response = await apiClient.get<ApiResponse<TagDistributionItem[]>>('/dashboard/tags', {
    params: { limit: 10 },
    timeout: DASHBOARD_REQUEST_TIMEOUT_MS,
  })
  return response.data.data
}
