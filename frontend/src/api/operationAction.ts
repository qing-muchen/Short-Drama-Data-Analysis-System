import apiClient from './axios'
import type { ApiResponse, Pagination } from '../types/api'
import type { ActionQuery, CreateActionRequest, OperationAction, OperationActionPage, OperationActionStatistics, OperationActionStatus } from '../types/operationAction'

export async function createOperationAction(payload: CreateActionRequest): Promise<OperationAction> {
  const response = await apiClient.post<ApiResponse<OperationAction>>('/operation-actions', payload)
  return response.data.data
}
export async function getOperationActions(params: ActionQuery = {}): Promise<OperationActionPage> {
  const response = await apiClient.get<ApiResponse<Pagination<OperationAction>>>('/operation-actions', { params })
  return response.data.data
}
export async function getOperationActionStatistics(): Promise<OperationActionStatistics> {
  const response = await apiClient.get<ApiResponse<OperationActionStatistics>>('/operation-actions/statistics')
  return response.data.data
}
export async function getOperationAction(actionId: number): Promise<OperationAction> {
  const response = await apiClient.get<ApiResponse<OperationAction>>(`/operation-actions/${actionId}`)
  return response.data.data
}
export async function updateOperationActionStatus(actionId: number, newStatus: OperationActionStatus, comment?: string): Promise<OperationAction> {
  const response = await apiClient.patch<ApiResponse<OperationAction>>(`/operation-actions/${actionId}/status`, { new_status: newStatus, comment })
  return response.data.data
}
export async function assignOperationAction(actionId: number, assigneeUserId: number): Promise<OperationAction> {
  const response = await apiClient.patch<ApiResponse<OperationAction>>(`/operation-actions/${actionId}/assign`, { assignee_user_id: assigneeUserId })
  return response.data.data
}
export async function addOperationActionComment(actionId: number, comment: string): Promise<unknown> {
  const response = await apiClient.post<ApiResponse<unknown>>(`/operation-actions/${actionId}/comments`, { comment })
  return response.data.data
}
