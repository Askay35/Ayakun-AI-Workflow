import { ACCESS_TOKEN_KEY, REFRESH_TOKEN_KEY, readLocal, writeLocal } from '~/utils/local-session'

export default defineNuxtPlugin(() => {
  const accessToken = useState<string | null>('ayakun_access', () => null)
  const refreshToken = useState<string | null>('ayakun_refresh', () => null)

  accessToken.value = readLocal(ACCESS_TOKEN_KEY)
  refreshToken.value = readLocal(REFRESH_TOKEN_KEY)

  // Migrate leftover cookie sessions once, then clear cookies.
  const cookieAccess = useCookie<string | null>('ayakun_access')
  const cookieRefresh = useCookie<string | null>('ayakun_refresh')
  if (!accessToken.value && cookieAccess.value) {
    accessToken.value = cookieAccess.value
    writeLocal(ACCESS_TOKEN_KEY, cookieAccess.value)
  }
  if (!refreshToken.value && cookieRefresh.value) {
    refreshToken.value = cookieRefresh.value
    writeLocal(REFRESH_TOKEN_KEY, cookieRefresh.value)
  }
  cookieAccess.value = null
  cookieRefresh.value = null

  watch(accessToken, (value) => writeLocal(ACCESS_TOKEN_KEY, value), { flush: 'sync' })
  watch(refreshToken, (value) => writeLocal(REFRESH_TOKEN_KEY, value), { flush: 'sync' })
})
