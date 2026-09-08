import apiClient from './axios'
import type { ApiResponse } from '../types/api'
import type { LoginRequest, LoginResponse, User } from '../types/auth'

export async function login(username: string, password: string): Promise<LoginResponse> {
  const payload: LoginRequest = { username, password }
  const response = await apiClient.post<ApiResponse<LoginResponse>>('/auth/login', payload)
  return response.data.data
}

export async function getCurrentUser(): Promise<User> {
  const response = await apiClient.get<ApiResponse<User>>('/auth/me')
  return response.data.data
}
