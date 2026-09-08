export const ACCESS_TOKEN_KEY = 'access_token'

export function readAccessToken(): string | null {
  if (typeof window === 'undefined') {
    return null
  }
  return window.localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function writeAccessToken(token: string): void {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(ACCESS_TOKEN_KEY, token)
  }
}

export function clearAccessToken(): void {
  if (typeof window !== 'undefined') {
    window.localStorage.removeItem(ACCESS_TOKEN_KEY)
  }
}
