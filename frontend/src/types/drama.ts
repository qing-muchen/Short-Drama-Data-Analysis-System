export type DramaStatus = 'DRAFT' | 'SERIALIZING' | 'COMPLETED' | 'INACTIVE'

export interface Drama {
  drama_id: number
  drama_code: string
  drama_name: string
  synopsis: string | null
  episode_count: number | null
  episode_duration_seconds: number | null
  premiere_date: string | null
  status: DramaStatus
  created_at: string
  updated_at: string
}

export interface DramaListParams {
  page: number
  page_size: number
  name_contains?: string
  status?: DramaStatus
}

export interface DramaCreate {
  drama_name: string
  synopsis?: string | null
  status: DramaStatus
}

export interface DramaUpdate {
  drama_name?: string
  synopsis?: string | null
  status?: DramaStatus
}

export type { Pagination } from './api'
