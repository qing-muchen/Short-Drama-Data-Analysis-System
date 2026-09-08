import apiClient from './axios'
import type { ApiResponse, Pagination } from '../types/api'
import type { ImportErrorItem, ImportJob, ImportType } from '../types/import'

export async function createImportJob(file: File, importType: ImportType): Promise<ImportJob> {
  const body = new FormData()
  body.append('import_type', importType)
  body.append('file', file, file.name)
  const response = await apiClient.post<ApiResponse<ImportJob>>('/import/jobs', body)
  return response.data.data
}

export async function getImportJob(importJobId: number): Promise<ImportJob> {
  const response = await apiClient.get<ApiResponse<ImportJob>>(`/import/jobs/${importJobId}`)
  return response.data.data
}

export async function getImportErrors(
  importJobId: number,
  page = 1,
  pageSize = 20,
): Promise<Pagination<ImportErrorItem>> {
  const response = await apiClient.get<ApiResponse<Pagination<ImportErrorItem>>>(
    `/import/jobs/${importJobId}/errors`,
    { params: { page, page_size: pageSize } },
  )
  return response.data.data
}

export async function confirmImportJob(importJobId: number): Promise<ImportJob> {
  const response = await apiClient.post<ApiResponse<ImportJob>>(
    `/import/jobs/${importJobId}/confirm`,
    { confirm: true },
  )
  return response.data.data
}
