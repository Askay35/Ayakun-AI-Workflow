import { PAGE_TITLES } from '~/utils/app-nav'

export function useAppTitle(title?: MaybeRefOrGetter<string | undefined>) {
  const route = useRoute()
  useHead({
    title: computed(() => {
      const override = title === undefined ? undefined : toValue(title)
      if (override) return override
      return PAGE_TITLES[String(route.name)] || 'Ayakun'
    })
  })
}
