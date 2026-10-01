import apiClient from './axios'
import type { ApiResponse } from '../types/api'
import type { ImportBatch } from '../types/batch-import'

export async function createImportBatch(batchCode?: string): Promise<ImportBatch> {
  const response = await apiClient.post<ApiResponse<ImportBatch>>('/import/batches', {
    batch_code: batchCode?.trim() || null,
  })
  return response.data.data
}

export async function uploadImportBatchFiles(
  importBatchId: number,
  files: File[],
): Promise<ImportBatch> {
  const body = new FormData()
  files.forEach((file) => body.append('files', file, file.name))
  const response = await apiClient.post<ApiResponse<ImportBatch>>(
    `/import/batches/${importBatchId}/files`,
    body,
  )
  return response.data.data
}

export async function validateImportBatch(importBatchId: number): Promise<ImportBatch> {
  const response = await apiClient.post<ApiResponse<ImportBatch>>(
    `/import/batches/${importBatchId}/validate`,
  )
  return response.data.data
}

export async function confirmImportBatch(importBatchId: number): Promise<ImportBatch> {
  const response = await apiClient.post<ApiResponse<ImportBatch>>(
    `/import/batches/${importBatchId}/confirm`,
    { confirm: true },
  )
  return response.data.data
}

export async function getImportBatch(importBatchId: number): Promise<ImportBatch> {
  const response = await apiClient.get<ApiResponse<ImportBatch>>(
    `/import/batches/${importBatchId}`,
  )
  return response.data.data
}
