import type { AuthTokens, User } from '~/types/api'

export const useAuth = () => {
  const api = useApi()
  const user = useState<User | null>('auth-user', () => null)
  const pending = useState('auth-pending', () => false)

  const accept = async (tokens: AuthTokens) => {
    api.accessToken.value = tokens.access_token
    api.refreshToken.value = tokens.refresh_token
    user.value = tokens.user
    console.log('user', user.value)
    await nextTick()
  }

  const load = async () => {
    if (!api.accessToken.value && !api.refreshToken.value) return null
    pending.value = true
    try {
      console.log('user 2', user.value)

      user.value = await api.auth.me()
      console.log('user 3', user.value)
      return user.value
    } catch {
      user.value = null
      return null
    } finally {
      pending.value = false
    }
  }

  const logout = async () => {
    try { await api.auth.logout() } finally {
      api.accessToken.value = null
      api.refreshToken.value = null
      user.value = null
      await navigateTo('/auth')
    }
  }

  return { user, pending, accept, load, logout, isAuthenticated: computed(() => Boolean(user.value)) }
}
