import axios from 'axios'

import apiClient from './axios'
import type { ApiResponse } from '../types/api'
import type {
  ReportCatalog,
  ReportDownload,
  ReportExportParams,
  ReportPreview,
  ReportPreviewParams,
  ReportingApiErrorBody,
} from '../types/reporting'

export class ReportingApiError extends Error {
  readonly status: number | undefined
  readonly code: string | undefined
  readonly details: Record<string, unknown> | null

  constructor(
    message: string,
    options: {
      status?: number
      code?: string
      details?: Record<string, unknown> | null
    } = {},
  ) {
    super(message)
    this.name = 'ReportingApiError'
    this.status = options.status
    this.code = options.code
    this.details = options.details ?? null
  }
}

function requestParams(
  params: ReportPreviewParams | ReportExportParams,
): Record<string, string | number | boolean> {
  const result: Record<string, string | number | boolean> = {
    report_type: params.report_type,
  }
  if (params.filters && Object.keys(params.filters).length > 0) {
    result.filters = JSON.stringify(params.filters)
  }
  if (params.analysis_as_of) {
    result.analysis_as_of = params.analysis_as_of
  }
  if ('page_size' in params && params.page_size != null) {
    result.page_size = params.page_size
  }
  if ('export_format' in params) {
    result.export_format = params.export_format
    if (params.confirmation != null) {
      result.confirmation = params.confirmation
    }
  }
  return result
}

function downloadFilename(contentDisposition: string | undefined, fallback: string): string {
  if (!contentDisposition) {
    return fallback
  }
  const encoded = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  const plain = contentDisposition.match(/filename="?([^";]+)"?/i)?.[1]
  let candidate = fallback
  try {
    candidate = encoded ? decodeURIComponent(encoded) : plain || fallback
  } catch {
    candidate = plain || fallback
  }
  return candidate.replace(/[\\/\r\n]/g, '_')
}

async function errorBody(value: unknown): Promise<ReportingApiErrorBody | null> {
  if (value instanceof Blob) {
    try {
      return JSON.parse(await value.text()) as ReportingApiErrorBody
    } catch {
      return null
    }
  }
  return typeof value === 'object' && value !== null ? (value as ReportingApiErrorBody) : null
}

export async function getReportCatalog(): Promise<ReportCatalog[]> {
  const response = await apiClient.get<ApiResponse<ReportCatalog[]>>('/reports/catalog')
  return response.data.data
}

export async function getReportPreview(params: ReportPreviewParams): Promise<ReportPreview> {
  const response = await apiClient.get<ApiResponse<ReportPreview>>('/reports/preview', {
    params: requestParams(params),
  })
  return response.data.data
}

export async function exportReport(params: ReportExportParams): Promise<ReportDownload> {
  try {
    const response = await apiClient.get<Blob>('/reports/export', {
      params: requestParams(params),
      responseType: 'blob',
    })
    const fallback = `${params.report_type.toLowerCase()}.${params.export_format.toLowerCase()}`
    const contentDisposition = response.headers['content-disposition']
    const contentType = response.headers['content-type']
    return {
      blob: response.data,
      filename: downloadFilename(
        typeof contentDisposition === 'string' ? contentDisposition : undefined,
        fallback,
      ),
      mime_type: typeof contentType === 'string' ? contentType : response.data.type,
    }
  } catch (error: unknown) {
    if (!axios.isAxiosError(error)) {
      throw error
    }
    const body = await errorBody(error.response?.data)
    throw new ReportingApiError(body?.message || '报告导出失败，请稍后重试。', {
      status: error.response?.status,
      code: body?.code,
      details: body?.details,
    })
  }
}
