import apiClient from './axios'
import type { ApiResponse, Pagination } from '../types/api'
import type { Drama, DramaCreate, DramaListParams, DramaUpdate } from '../types/drama'

export async function getDramas(params: DramaListParams): Promise<Pagination<Drama>> {
  const response = await apiClient.get<ApiResponse<Pagination<Drama>>>('/dramas', { params })
  return response.data.data
}

export async function createDrama(payload: DramaCreate): Promise<Drama> {
  const response = await apiClient.post<ApiResponse<Drama>>('/dramas', payload)
  return response.data.data
}

export async function updateDrama(dramaId: number, payload: DramaUpdate): Promise<Drama> {
  const response = await apiClient.put<ApiResponse<Drama>>(`/dramas/${dramaId}`, payload)
  return response.data.data
}

export async function deactivateDrama(dramaId: number): Promise<Drama> {
  const response = await apiClient.delete<ApiResponse<Drama>>(`/dramas/${dramaId}`)
  return response.data.data
}
