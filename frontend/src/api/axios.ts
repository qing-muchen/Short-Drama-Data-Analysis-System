import axios, { type AxiosError } from 'axios'

import { clearAccessToken, readAccessToken } from '../utils/auth-storage'

type UnauthorizedHandler = () => void

let unauthorizedHandler: UnauthorizedHandler | null = null

function isCurrentUserRequest(url: string | undefined): boolean {
  return url != null && /\/auth\/me(?:[?#]|$)/.test(url)
}

export function setUnauthorizedHandler(handler: UnauthorizedHandler): void {
  unauthorizedHandler = handler
}

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 10_000,
})

apiClient.interceptors.request.use((config) => {
  const token = readAccessToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Only /auth/me authoritatively validates the current login session. A 401
    // from a business request must not invalidate other concurrent requests.
    if (error.response?.status === 401 && isCurrentUserRequest(error.config?.url)) {
      clearAccessToken()
      unauthorizedHandler?.()
    }
    return Promise.reject(error)
  },
)

export default apiClient
