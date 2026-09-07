export default defineNuxtRouteMiddleware(async () => {
  const auth = useAuth()
  const api = useApi()

  if (auth.user.value) return

  const hasSession = Boolean(api.accessToken.value || api.refreshToken.value)
  if (!hasSession) return navigateTo('/login')

  await auth.load()
  if (auth.user.value) return

  // Tokens exist but SSR couldn't reach the API — let the client retry instead of logging out
  if (import.meta.server && (api.accessToken.value || api.refreshToken.value)) return

  return navigateTo('/login')
})
