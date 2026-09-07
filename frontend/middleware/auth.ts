export default defineNuxtRouteMiddleware(async () => {
  const auth = useAuth()
  if (!auth.user.value) await auth.load()
  if (!auth.user.value) return navigateTo('/auth')
})
