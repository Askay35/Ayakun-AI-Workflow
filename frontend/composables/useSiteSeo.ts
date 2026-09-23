/** SEO для публичных страниц: абсолютные URL, сниппет и favicon для поисковиков. */
export function useSiteSeo() {
  const { locale, t } = useI18n()
  const config = useRuntimeConfig()
  const route = useRoute()

  const siteUrl = String(config.public.siteUrl || 'https://ayakun.ru').replace(/\/$/, '')
  const title = computed(() => t('meta.siteTitle'))
  const description = computed(() => t('meta.siteDescription'))
  const canonical = computed(() => {
    const path = route.path === '/' ? '' : route.path.replace(/\/$/, '')
    return `${siteUrl}${path}`
  })
  const ogImage = `${siteUrl}/og-image.png`

  useSeoMeta({
    description: () => description.value,
    ogTitle: () => title.value,
    ogDescription: () => description.value,
    ogType: 'website',
    ogUrl: () => canonical.value,
    ogImage,
    ogImageWidth: 1200,
    ogImageHeight: 630,
    ogLocale: () => (locale.value === 'en' ? 'en_US' : 'ru_RU'),
    ogSiteName: 'Ayakun',
    twitterCard: 'summary_large_image',
    twitterTitle: () => title.value,
    twitterDescription: () => description.value,
    twitterImage: ogImage
  })

  useHead({
    htmlAttrs: { lang: locale },
    titleTemplate: (pageTitle?: string) => {
      const site = title.value
      return !pageTitle || pageTitle === 'Ayakun' || pageTitle === site ? site : `${pageTitle} · Ayakun`
    },
    link: [
      { key: 'canonical', rel: 'canonical', href: () => canonical.value },
      // Google в выдаче хочет иконку кратную 48px; абсолютный URL упрощает обход.
      { key: 'icon-48', rel: 'icon', type: 'image/png', sizes: '48x48', href: `${siteUrl}/favicon-48x48.png` },
      { key: 'icon-96', rel: 'icon', type: 'image/png', sizes: '96x96', href: `${siteUrl}/favicon-96x96.png` },
      { key: 'icon-192', rel: 'icon', type: 'image/png', sizes: '192x192', href: `${siteUrl}/favicon-192x192.png` },
      { key: 'icon-ico', rel: 'icon', type: 'image/x-icon', href: `${siteUrl}/favicon.ico` },
      { key: 'shortcut-icon', rel: 'shortcut icon', href: `${siteUrl}/favicon.ico` },
      { key: 'apple-touch-icon', rel: 'apple-touch-icon', sizes: '180x180', href: `${siteUrl}/apple-touch-icon.png` }
    ],
    script: [
      {
        key: 'ld-website',
        type: 'application/ld+json',
        innerHTML: () =>
          JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'WebSite',
            name: 'Ayakun',
            url: siteUrl,
            description: description.value,
            inLanguage: locale.value === 'en' ? 'en' : 'ru',
            potentialAction: {
              '@type': 'RegisterAction',
              target: `${siteUrl}/login`
            }
          })
      },
      {
        key: 'ld-org',
        type: 'application/ld+json',
        innerHTML: () =>
          JSON.stringify({
            '@context': 'https://schema.org',
            '@type': 'Organization',
            name: 'Ayakun',
            url: siteUrl,
            logo: `${siteUrl}/favicon-192x192.png`,
            description: description.value
          })
      }
    ]
  })
}
