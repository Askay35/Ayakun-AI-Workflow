import { PAGE_TITLE_KEYS } from '~/utils/app-nav'

export function useAppTitle(title?: MaybeRefOrGetter<string | undefined>) {
  const route = useRoute()
  const { t } = useI18n()
  useHead({
    title: computed(() => {
      const override = title === undefined ? undefined : toValue(title)
      if (override) return override
      const key = PAGE_TITLE_KEYS[String(route.name)]
      return key ? t(key) : 'Ayakun'
    })
  })
}
