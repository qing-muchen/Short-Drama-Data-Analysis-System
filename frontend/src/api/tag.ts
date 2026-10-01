import apiClient from './axios'
import type { ApiResponse, Pagination } from '../types/api'
import type { MasterListParams, Tag, TagWrite } from '../types/master'

export async function getTags(params: MasterListParams): Promise<Pagination<Tag>> {
  const response = await apiClient.get<ApiResponse<Pagination<Tag>>>('/tags', { params })
  return response.data.data
}

export async function createTag(payload: TagWrite): Promise<Tag> {
  const response = await apiClient.post<ApiResponse<Tag>>('/tags', payload)
  return response.data.data
}

export async function updateTag(tagId: number, payload: Partial<TagWrite>): Promise<Tag> {
  const response = await apiClient.put<ApiResponse<Tag>>(`/tags/${tagId}`, payload)
  return response.data.data
}

export async function deactivateTag(tagId: number): Promise<Tag> {
  const response = await apiClient.delete<ApiResponse<Tag>>(`/tags/${tagId}`)
  return response.data.data
}
