export type DramaStatus = 'DRAFT' | 'SERIALIZING' | 'COMPLETED' | 'INACTIVE'

export interface DramaTag {
  tag_id: number
  tag_name: string
}

export interface DramaPlatform {
  platform_id: number
  platform_name: string
}

export interface Drama {
  drama_id: number
  drama_code: string
  drama_name: string
  synopsis: string | null
  episode_count: number | null
  episode_duration_seconds: number | null
  premiere_date: string | null
  status: DramaStatus
  tags: DramaTag[]
  platforms: DramaPlatform[]
  created_at: string
  updated_at: string
}

export interface DramaListParams {
  page: number
  page_size: number
  name_contains?: string
  status?: DramaStatus
  tag_ids?: string
}

export interface DramaCreate {
  drama_name: string
  synopsis?: string | null
  status: DramaStatus
  tags: number[]
}

export interface DramaUpdate {
  drama_name?: string
  synopsis?: string | null
  status?: DramaStatus
  tags?: number[]
}

export type { Pagination } from './api'
