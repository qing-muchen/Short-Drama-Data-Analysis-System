export type UserRole = 'ADMINISTRATOR' | 'USER'
export type UserStatus = 'ACTIVE' | 'INACTIVE'

export interface User {
  user_id: number
  username: string
  display_name: string | null
  role_code: UserRole
  status: UserStatus
  last_login_at: string | null
  created_at: string
  updated_at: string
}

export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
  expires_in_seconds: number
}
