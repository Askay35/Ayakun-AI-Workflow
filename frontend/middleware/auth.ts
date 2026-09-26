import { rememberAfterLogin } from '~/utils/after-login'

export default defineNuxtRouteMiddleware(async (to) => {
  // Tokens live in localStorage — only available on the client.
  if (import.meta.server) return

  const auth = useAuth()
  const api = useApi()

  if (!auth.user.value) {
    const hasSession = Boolean(api.accessToken.value || api.refreshToken.value)
    if (!hasSession) {
      rememberAfterLogin(to.fullPath)
      return navigateTo('/login')
    }

    await auth.load()
    if (!auth.user.value) {
      rememberAfterLogin(to.fullPath)
      return navigateTo('/login')
    }
  }

  // Новый пользователь сначала проходит короткий опрос и попадает сразу в подходящую цепочку.
  // Кто пришёл по ссылке на шаблон, уже выбрал, с чего начать, — опрос ему не нужен.
  const fromTemplate = to.path.startsWith('/templates/')
  if (!auth.user.value.onboarded_at && !fromTemplate && to.path !== '/onboarding') return navigateTo('/onboarding')
})
