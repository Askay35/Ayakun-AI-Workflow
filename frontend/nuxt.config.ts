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
      meta: [{ name: 'description', content: 'Визуальные AI-цепочки: поиск, обработка и доставка без кода.' }],
      link: [
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
