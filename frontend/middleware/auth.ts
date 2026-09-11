export default defineNuxtRouteMiddleware(async () => {
  // Tokens live in localStorage — only available on the client.
  if (import.meta.server) return

  const auth = useAuth()
  const api = useApi()

  if (auth.user.value) return

  const hasSession = Boolean(api.accessToken.value || api.refreshToken.value)
  if (!hasSession) return navigateTo('/login')

  await auth.load()
  if (auth.user.value) return

  return navigateTo('/login')
})
