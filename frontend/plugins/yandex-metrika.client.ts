const METRIKA_ID = 112724783

declare global {
  interface Window {
    ym?: (id: number, method: string, ...args: unknown[]) => void
  }
}

export default defineNuxtPlugin(() => {
  useHead({
    script: [
      {
        key: 'yandex-metrika',
        type: 'text/javascript',
        children: `
(function(m,e,t,r,i,k,a){
  m[i]=m[i]||function(){(m[i].a=m[i].a||[]).push(arguments)};
  m[i].l=1*new Date();
  for (var j = 0; j < document.scripts.length; j++) {if (document.scripts[j].src === r) { return; }}
  k=e.createElement(t),a=e.getElementsByTagName(t)[0],k.async=1,k.src=r,a.parentNode.insertBefore(k,a)
})(window, document,'script','https://mc.yandex.ru/metrika/tag.js?id=${METRIKA_ID}', 'ym');
ym(${METRIKA_ID}, 'init', {ssr:true, webvisor:true, clickmap:true, ecommerce:"dataLayer", referrer: document.referrer, url: location.href, accurateTrackBounce:true, trackLinks:true});
        `.trim()
      }
    ],
    noscript: [
      {
        key: 'yandex-metrika-noscript',
        children: `<div><img src="https://mc.yandex.ru/watch/${METRIKA_ID}" style="position:absolute; left:-9999px;" alt="" /></div>`
      }
    ]
  })

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
