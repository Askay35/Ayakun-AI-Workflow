export const ACCESS_TOKEN_KEY = 'ayakun_access'
export const REFRESH_TOKEN_KEY = 'ayakun_refresh'
export const ADMIN_AUTH_KEY = 'ayakun_admin_auth'

export const readLocal = (key: string): string | null => {
  if (!import.meta.client) return null
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

export const writeLocal = (key: string, value: string | null | undefined) => {
  if (!import.meta.client) return
  try {
    if (value == null || value === '') localStorage.removeItem(key)
    else localStorage.setItem(key, value)
  } catch {
    // ignore quota / private mode write failures
  }
}
