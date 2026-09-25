export const PAGE_TITLE_KEYS: Record<string, string> = {
  index: 'titles.index',
  login: 'titles.login',
  dashboard: 'titles.dashboard',
  workflows: 'titles.workflows',
  'workflows-id': 'titles.editor',
  runs: 'titles.runs',
  'runs-id': 'titles.run',
  billing: 'titles.billing',
  referrals: 'titles.referrals',
  profile: 'titles.profile',
  pricing: 'titles.pricing',
  terms: 'titles.terms',
  privacy: 'titles.privacy',
  docs: 'titles.docs',
  contacts: 'titles.contacts',
  delivery: 'titles.delivery',
  'auth-google-callback': 'titles.googleCallback'
}

export const APP_NAV_ITEMS = [
  { key: 'overview', icon: 'i-lucide-layout-dashboard', to: '/dashboard' },
  { key: 'workflows', icon: 'i-lucide-workflow', to: '/workflows' },
  { key: 'runs', icon: 'i-lucide-activity', to: '/runs' },
  { key: 'docs', icon: 'i-lucide-book-open', to: '/docs' },
  { key: 'billing', icon: 'i-lucide-wallet', to: '/billing' },
  { key: 'referrals', icon: 'i-lucide-gift', to: '/referrals' },
  { key: 'profile', icon: 'i-lucide-user', to: '/profile' }
] as const
