export const PAGE_TITLES: Record<string, string> = {
  index: 'Yakun',
  login: 'Вход',
  dashboard: 'Обзор',
  workflows: 'Цепочки',
  'workflows-id': 'Редактор',
  runs: 'Запуски',
  'runs-id': 'Запуск',
  billing: 'Биллинг',
  profile: 'Профиль',
  pricing: 'Тарифы',
  terms: 'Условия',
  'auth-google-callback': 'Вход'
}

export const APP_NAV_ITEMS = [
  { label: 'Обзор', icon: 'i-lucide-layout-dashboard', to: '/dashboard' },
  { label: 'Цепочки', icon: 'i-lucide-workflow', to: '/workflows' },
  { label: 'Запуски', icon: 'i-lucide-activity', to: '/runs' },
  { label: 'Биллинг', icon: 'i-lucide-wallet', to: '/billing' },
  { label: 'Профиль', icon: 'i-lucide-user', to: '/profile' }
] as const
