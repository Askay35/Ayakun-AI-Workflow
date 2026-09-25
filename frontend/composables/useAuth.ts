import type { AuthTokens, User } from '~/types/api'
import { forgetReferral, pendingReferral } from '~/utils/referral'

export const useAuth = () => {
  const api = useApi()
  const user = useState<User | null>('auth-user', () => null)
  const pending = useState('auth-pending', () => false)

  const claimReferral = async () => {
    const code = pendingReferral()
    if (!code) return
    try {
      await api.referrals.claim(code)
    } catch {
      // Код чужой, старый или аккаунт не новый — приглашение просто не привязывается.
    }
    forgetReferral()
  }

  const accept = async (tokens: AuthTokens) => {
    api.accessToken.value = tokens.access_token
    api.refreshToken.value = tokens.refresh_token
    user.value = tokens.user
    await nextTick()
    await claimReferral()
  }

  const clearSession = () => {
    api.accessToken.value = null
    api.refreshToken.value = null
    user.value = null
  }

  const load = async () => {
    if (!api.accessToken.value && !api.refreshToken.value) return null
    pending.value = true
    try {
      user.value = await api.auth.me()
      return user.value
    } catch (error: any) {
      const status = error?.statusCode || error?.status
      // Only drop the session on confirmed auth failure, not SSR/network blips
      if (status === 401 || status === 403) {
        clearSession()
      }
      return null
    } finally {
      pending.value = false
    }
  }

  const logout = async () => {
    try { await api.auth.logout() } finally {
      clearSession()
      await navigateTo('/login')
    }
  }

  return { user, pending, accept, load, logout, clearSession, isAuthenticated: computed(() => Boolean(user.value)) }
}
