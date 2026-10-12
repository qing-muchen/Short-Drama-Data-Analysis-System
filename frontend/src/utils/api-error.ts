import axios from 'axios'
import type { ApiErrorBody } from '../types/api'

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    return error.response?.data?.message || fallback
  }
  return error instanceof Error ? error.message : fallback
}

export function getApiErrorStatus(error: unknown): number | undefined {
  return axios.isAxiosError<ApiErrorBody>(error) ? error.response?.status : undefined
}

export function getApiErrorDetail(error: unknown, key: string): unknown {
  if (!axios.isAxiosError<ApiErrorBody>(error)) return undefined
  return error.response?.data?.details?.[key]
}
