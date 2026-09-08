import apiClient from './axios'
import type { ApiResponse, Pagination } from '../types/api'
import type { Actor, ActorWrite, MasterListParams } from '../types/master'

export async function getActors(params: MasterListParams): Promise<Pagination<Actor>> {
  const response = await apiClient.get<ApiResponse<Pagination<Actor>>>('/actors', { params })
  return response.data.data
}

export async function createActor(payload: ActorWrite): Promise<Actor> {
  const response = await apiClient.post<ApiResponse<Actor>>('/actors', payload)
  return response.data.data
}

export async function updateActor(actorId: number, payload: ActorWrite): Promise<Actor> {
  const response = await apiClient.put<ApiResponse<Actor>>(`/actors/${actorId}`, payload)
  return response.data.data
}

export async function deactivateActor(actorId: number): Promise<Actor> {
  const response = await apiClient.delete<ApiResponse<Actor>>(`/actors/${actorId}`)
  return response.data.data
}
