const METRIKA_ID = 112724783

declare global {
  interface Window {
    ym?: ((id: number, method: string, ...args: unknown[]) => void) & {
      a?: unknown[][]
      l?: number
    }
  }
}

export default defineNuxtPlugin(() => {
  const src = `https://mc.yandex.ru/metrika/tag.js?id=${METRIKA_ID}`
  if (![...document.scripts].some(script => script.src === src)) {
    window.ym = window.ym || function (...args: unknown[]) {
      ;(window.ym!.a = window.ym!.a || []).push(args)
    }
    window.ym.l = Date.now()
    const script = document.createElement('script')
    script.async = true
    script.src = src
    document.head.appendChild(script)
  }

  window.ym?.(METRIKA_ID, 'init', {
    ssr: true,
    webvisor: true,
    clickmap: true,
    ecommerce: 'dataLayer',
    referrer: document.referrer,
    url: location.href,
    accurateTrackBounce: true,
    trackLinks: true
  })

  const noscript = document.createElement('noscript')
  noscript.innerHTML = `<div><img src="https://mc.yandex.ru/watch/${METRIKA_ID}" style="position:absolute; left:-9999px;" alt="" /></div>`
  document.body.appendChild(noscript)

  const router = useRouter()
  let ready = false
  router.afterEach((to) => {
    if (!ready) {
      ready = true
      return
    }
    window.ym?.(METRIKA_ID, 'hit', to.fullPath)
  })
})
