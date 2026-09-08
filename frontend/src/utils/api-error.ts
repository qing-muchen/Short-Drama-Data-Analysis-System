import axios from 'axios'
import type { ApiErrorBody } from '../types/api'

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError<ApiErrorBody>(error)) {
    return error.response?.data?.message || fallback
  }
  return error instanceof Error ? error.message : fallback
}
