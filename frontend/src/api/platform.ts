import apiClient from './axios'
import type { ApiResponse, Pagination } from '../types/api'
import type { MasterListParams, Platform, PlatformWrite } from '../types/master'

export async function getPlatforms(params: MasterListParams): Promise<Pagination<Platform>> {
  const response = await apiClient.get<ApiResponse<Pagination<Platform>>>('/platforms', { params })
  return response.data.data
}

export async function createPlatform(payload: PlatformWrite): Promise<Platform> {
  const response = await apiClient.post<ApiResponse<Platform>>('/platforms', payload)
  return response.data.data
}

export async function updatePlatform(
  platformId: number,
  payload: PlatformWrite,
): Promise<Platform> {
  const response = await apiClient.put<ApiResponse<Platform>>(`/platforms/${platformId}`, payload)
  return response.data.data
}

export async function deactivatePlatform(platformId: number): Promise<Platform> {
  const response = await apiClient.delete<ApiResponse<Platform>>(`/platforms/${platformId}`)
  return response.data.data
}
