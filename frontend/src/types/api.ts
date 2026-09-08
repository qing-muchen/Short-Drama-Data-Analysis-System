export interface ApiResponse<T> {
  data: T
  message: string
}

export interface Pagination<T> {
  page: number
  page_size: number
  total: number
  items: T[]
}

export interface ApiErrorBody {
  code?: string
  message?: string
  details?: Record<string, unknown> | null
}
