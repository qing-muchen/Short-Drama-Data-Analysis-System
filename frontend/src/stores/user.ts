import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

import { getCurrentUser, login as loginRequest } from '../api/auth'
import type { User } from '../types/auth'
import { clearAccessToken, readAccessToken, writeAccessToken } from '../utils/auth-storage'

export const useUserStore = defineStore('user', () => {
  const token = ref<string | null>(readAccessToken())
  const currentUser = ref<User | null>(null)
  const isAuthenticated = computed(() => token.value !== null && token.value.length > 0)

  function persistToken(value: string | null): void {
    token.value = value
    if (value) {
      writeAccessToken(value)
    } else {
      clearAccessToken()
    }
  }

  async function login(username: string, password: string): Promise<User> {
    const response = await loginRequest(username, password)
    persistToken(response.access_token)
    try {
      return await fetchCurrentUser()
    } catch (error: unknown) {
      logout()
      throw error
    }
  }

  async function fetchCurrentUser(): Promise<User> {
    if (!isAuthenticated.value) {
      throw new Error('Authentication token is required')
    }
    const user = await getCurrentUser()
    currentUser.value = user
    return user
  }

  function logout(): void {
    persistToken(null)
    currentUser.value = null
  }

  return {
    token,
    currentUser,
    isAuthenticated,
    login,
    logout,
    fetchCurrentUser,
  }
})
