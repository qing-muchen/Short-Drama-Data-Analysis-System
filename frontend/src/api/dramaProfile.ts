import apiClient from './axios'
import type { ApiResponse } from '../types/api'
import type { DramaProfileResponse } from '../types/dramaProfile'

export async function getDramaProfile(dramaId: number): Promise<DramaProfileResponse> {
  const response = await apiClient.get<ApiResponse<DramaProfileResponse>>(
    `/dramas/${dramaId}/profile`,
  )
  return response.data.data
}
