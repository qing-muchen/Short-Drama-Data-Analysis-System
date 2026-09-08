import axios from 'axios'

interface ErrorBody {
  message?: string
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError<ErrorBody>(error)) {
    return error.response?.data?.message || fallback
  }
  return error instanceof Error ? error.message : fallback
}
