export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  modules: ['@nuxt/ui'],
  css: ['~/assets/css/main.css', '@vue-flow/core/dist/style.css', '@vue-flow/core/dist/theme-default.css'],
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
      title: 'Ayakun — визуальная автоматизация с ИИ без кода',
      meta: [
        {
          name: 'description',
          content: 'Соберите на холсте цепочку: поиск данных → анализ нейросетью → нужное действие. Результат приходит туда, куда вы укажете. Просто, наглядно и быстро. Попробуйте бесплатно — даем 200 credits при регистрации.'
        },
        {
          property: 'og:title',
          content: 'Ayakun — визуальная автоматизация с ИИ без кода'
        },
        {
          property: 'og:description',
          content: 'Соберите на холсте цепочку: поиск данных → анализ нейросетью → нужное действие. Результат приходит туда, куда вы укажете. Просто, наглядно и быстро. Попробуйте бесплатно — даем 200 credits при регистрации.'
        },
        { property: 'og:type', content: 'website' }
      ],
      link: [
        { rel: 'icon', type: 'image/x-icon', href: '/favicon.ico' },
        { rel: 'shortcut icon', type: 'image/x-icon', href: '/favicon.ico' },
        { rel: 'apple-touch-icon', href: '/logo.ico' },
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
