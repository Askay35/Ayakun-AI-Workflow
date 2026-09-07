export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  modules: ['@nuxt/ui'],
  css: ['~/assets/css/main.css', '@vue-flow/core/dist/style.css', '@vue-flow/core/dist/theme-default.css'],
  runtimeConfig: {
    public: {
      apiBase: 'http://localhost:8001/api/v1'
    }
  },
  app: {
    head: {
      title: 'Yakun — AI-цепочки без кода',
      meta: [{ name: 'description', content: 'Создавайте и запускайте AI-цепочки визуально.' }]
    }
  },
  typescript: { strict: true, typeCheck: true }
})
