import { rememberReferral } from '~/utils/referral'

// Код из ссылки ?ref=… запоминаем до входа: привязка идёт после регистрации.
export default defineNuxtPlugin(() => {
  const router = useRouter()
  rememberReferral(router.currentRoute.value.query.ref)
  router.afterEach(to => rememberReferral(to.query.ref))
})
