export type EntityStatus = 'ACTIVE' | 'INACTIVE'

export interface Actor {
  actor_id: number
  actor_name: string
  profile_note: string | null
  status: EntityStatus
  created_at: string
  updated_at: string
}

export interface Platform {
  platform_id: number
  platform_name: string
  description: string | null
  status: EntityStatus
  created_at: string
  updated_at: string
}

export interface MasterListParams {
  page: number
  page_size: number
  name_contains?: string
  status?: EntityStatus
}

export interface ActorWrite {
  actor_name: string
  profile_note?: string | null
  status: EntityStatus
}

export interface PlatformWrite {
  platform_name: string
  description?: string | null
  status: EntityStatus
}

export type { Pagination } from './api'
