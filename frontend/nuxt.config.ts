export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  modules: ['@nuxt/ui'],
  css: ['~/assets/css/main.css', '~/assets/css/landing.css', '@vue-flow/core/dist/style.css', '@vue-flow/core/dist/theme-default.css'],
  runtimeConfig: {
    // Server-only (NUXT_API_BASE) — docker internal hostname
    apiBase: '',
    public: {
      // Browser (NUXT_PUBLIC_API_BASE)
      siteUrl: 'https://ayakun.ru',
      apiBase: 'http://localhost:8000/api/v1'
    }
  },
  routeRules: {
    '/auth': { redirect: '/login' },
    '/dashboard': { ssr: false },
    '/workflows': { ssr: false },
    '/workflows/**': { ssr: false },
    '/runs': { ssr: false },
    '/runs/**': { ssr: false },
    '/billing': { ssr: false },
    '/profile': { ssr: false },
    '/admin': { ssr: false }
  },
  app: {
    head: {
      // Статичный fallback в HTML до гидрации: Googlebot читает этот кусок, а не только JS.
      title: 'Ayakun — визуальная автоматизация с ИИ без кода',
      meta: [
        {
          name: 'description',
          content: 'Соберите на холсте цепочку: поиск данных → анализ нейросетью → нужное действие. Результат приходит туда, куда вы укажете. Просто, наглядно и быстро. Попробуйте бесплатно — даем 200 токенов при регистрации.'
        },
        {
          property: 'og:title',
          content: 'Ayakun — визуальная автоматизация с ИИ без кода'
        },
        {
          property: 'og:description',
          content: 'Соберите на холсте цепочку: поиск данных → анализ нейросетью → нужное действие. Результат приходит туда, куда вы укажете. Просто, наглядно и быстро. Попробуйте бесплатно — даем 200 токенов при регистрации.'
        },
        { property: 'og:type', content: 'website' },
        { property: 'og:url', content: 'https://ayakun.ru/' },
        { property: 'og:image', content: 'https://ayakun.ru/og-image.png' },
        { property: 'og:locale', content: 'ru_RU' },
        { property: 'og:site_name', content: 'Ayakun' },
        { name: 'twitter:card', content: 'summary_large_image' },
        { name: 'twitter:image', content: 'https://ayakun.ru/og-image.png' }
      ],
      link: [
        { rel: 'canonical', href: 'https://ayakun.ru/' },
        // Google требует иконку кратную 48×48; .ico раньше содержал только 16/32.
        { rel: 'icon', type: 'image/png', sizes: '48x48', href: 'https://ayakun.ru/favicon-48x48.png' },
        { rel: 'icon', type: 'image/png', sizes: '96x96', href: 'https://ayakun.ru/favicon-96x96.png' },
        { rel: 'icon', type: 'image/png', sizes: '192x192', href: 'https://ayakun.ru/favicon-192x192.png' },
        { rel: 'icon', type: 'image/x-icon', href: 'https://ayakun.ru/favicon.ico' },
        { rel: 'shortcut icon', href: 'https://ayakun.ru/favicon.ico' },
        { rel: 'apple-touch-icon', sizes: '180x180', href: 'https://ayakun.ru/apple-touch-icon.png' },
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Unbounded:wght@600;700&display=swap'
        }
      ]
    }
  },
  typescript: { strict: true, typeCheck: true }
})
