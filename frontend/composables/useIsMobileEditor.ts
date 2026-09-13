const MOBILE_EDITOR_QUERY = '(max-width: 900px)'

export function useIsMobileEditor() {
  const isMobileEditor = ref(false)

  const sync = (matches: boolean) => {
    isMobileEditor.value = matches
  }

  if (import.meta.client) {
    const media = window.matchMedia(MOBILE_EDITOR_QUERY)
    sync(media.matches)
    const onChange = (event: MediaQueryListEvent) => sync(event.matches)
    media.addEventListener('change', onChange)
    onBeforeUnmount(() => media.removeEventListener('change', onChange))
  }

  return isMobileEditor
}
