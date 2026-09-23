<script setup lang="ts">
import type {
  AdminConfig,
  AdminPaymentRecord,
  AdminRunRecord,
  AdminUserRecord,
  AdminWorkflowRecord,
  Plan,
  PricingRate
} from '~/types/api'
import { apiErrorMessage } from '~/composables/useApi'
import type { AdminColumn, AdminField, AdminSelectOption } from '~/components/AdminRecordsTab.vue'
import { ADMIN_AUTH_KEY, readLocal, writeLocal } from '~/utils/local-session'
import { formatCredits } from '~/utils/credits'
import { ledgerDescription } from '~/utils/ledger'
import { statusColor, statusLabel } from '~/utils/run-status'

definePageMeta({ layout: false, ssr: false })
useHead({ title: 'Администрирование' })

const PAGE_SIZE = 20
const VISION_PROVIDERS = [
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'GigaChat', value: 'gigachat' }
]
const CREDIT_SETTING_KEYS = new Set([
  'image_generation_credits',
  'image_recognition_credits_deepseek',
  'image_recognition_credits_gigachat',
  'audio_minute_credits'
])
const api = useApi()
const auth = useAuth()
const toast = useToast()
const login = ref('')
const password = ref('')
const credentials = ref('')
const loading = ref(false)
const config = ref<AdminConfig>()
const tab = ref('users')

const searchRates = computed(() =>
  (config.value?.pricing || []).filter(rate => rate.provider === 'serper')
)

const tabs = [
  { label: 'Пользователи', icon: 'i-lucide-users', value: 'users', slot: 'users' },
  { label: 'Транзакции', icon: 'i-lucide-receipt', value: 'payments', slot: 'payments' },
  { label: 'Цепочки', icon: 'i-lucide-workflow', value: 'workflows', slot: 'workflows' },
  { label: 'Запуски', icon: 'i-lucide-play', value: 'runs', slot: 'runs' },
  { label: 'Настройки', icon: 'i-lucide-sliders-horizontal', value: 'settings', slot: 'settings' }
]

const load = async () => {
  if (!credentials.value) return
  loading.value = true
  try {
    config.value = structuredClone(await api.admin.config(credentials.value))
  } catch {
    credentials.value = ''
    writeLocal(ADMIN_AUTH_KEY, null)
    toast.add({ title: 'Неверный логин или пароль', color: 'error' })
  } finally {
    loading.value = false
  }
}
const signIn = async () => {
  credentials.value = btoa(`${login.value}:${password.value}`)
  writeLocal(ADMIN_AUTH_KEY, credentials.value)
  await load()
}
const signOut = () => {
  credentials.value = ''
  password.value = ''
  config.value = undefined
  writeLocal(ADMIN_AUTH_KEY, null)
}
const saveSearchRate = async (rate: PricingRate) => {
  try {
    Object.assign(rate, await api.admin.updatePricing(credentials.value, rate))
    toast.add({ title: 'Цена поиска сохранена', color: 'success' })
  } catch {
    toast.add({ title: 'Не удалось сохранить цену', color: 'error' })
  }
}
const savePlan = async (plan: Plan) => {
  try {
    Object.assign(plan, await api.admin.updatePlan(credentials.value, plan))
    toast.add({ title: 'Тариф сохранён', color: 'success' })
  } catch {
    toast.add({ title: 'Не удалось сохранить тариф', color: 'error' })
  }
}
const isCreditSetting = (key: string) => CREDIT_SETTING_KEYS.has(key)
const saveSetting = async (setting: AdminConfig['settings'][number]) => {
  try {
    if (isCreditSetting(setting.key)) setting.value = Number(setting.value)
    Object.assign(setting, await api.admin.updateSetting(credentials.value, setting))
    toast.add({ title: 'Настройка сохранена', color: 'success' })
  } catch {
    toast.add({ title: 'Не удалось сохранить настройку', color: 'error' })
  }
}

const formatDate = (value?: string | null) => {
  if (!value) return '—'
  return new Date(value).toLocaleString('ru', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}
const shortId = (value: string | number) => {
  const text = String(value)
  return text.length > 12 ? `${text.slice(0, 8)}…` : text
}
const identityLabel = (provider: string) => (
  { email: 'Email', google: 'Google', telegram: 'Telegram' } as Record<string, string>
)[provider] || provider

const paymentStatusLabel = (status: string) => (
  { pending: 'Ожидает', succeeded: 'Оплачен', waiting_for_capture: 'Ожидает списания', canceled: 'Отменён' } as Record<string, string>
)[status] || status
const paymentStatusColor = (status: string) => {
  if (status === 'succeeded') return 'success' as const
  if (status === 'canceled') return 'error' as const
  if (status === 'waiting_for_capture') return 'warning' as const
  return 'neutral' as const
}
const workflowStatusLabel = (status: string) => (
  { draft: 'Черновик', published: 'Опубликована', archived: 'Архив' } as Record<string, string>
)[status] || status
const workflowStatusColor = (status: string) => {
  if (status === 'published') return 'success' as const
  if (status === 'archived') return 'neutral' as const
  return 'info' as const
}

const userQ = ref('')
const userStatus = ref('')
const userPage = ref(1)
const users = ref<AdminUserRecord[]>([])
const usersTotal = ref(0)
const usersLoading = ref(false)
const usersSaving = ref(false)
const usersDeleting = ref(false)
const impersonatingId = ref<number>()
const editingUser = ref<AdminUserRecord | null>(null)

const paymentQ = ref('')
const paymentStatus = ref('')
const paymentPage = ref(1)
const payments = ref<AdminPaymentRecord[]>([])
const paymentsTotal = ref(0)
const paymentsLoading = ref(false)
const paymentsSaving = ref(false)
const paymentsDeleting = ref(false)

const workflowQ = ref('')
const workflowStatus = ref('')
const workflowPage = ref(1)
const workflows = ref<AdminWorkflowRecord[]>([])
const workflowsTotal = ref(0)
const workflowsLoading = ref(false)
const workflowsSaving = ref(false)
const workflowsDeleting = ref(false)

const runQ = ref('')
const runStatus = ref('')
const runPage = ref(1)
const runs = ref<AdminRunRecord[]>([])
const runsTotal = ref(0)
const runsLoading = ref(false)
const runsSaving = ref(false)
const runsDeleting = ref(false)

const cleanQuery = (query: Record<string, string | number | undefined>) =>
  Object.fromEntries(Object.entries(query).filter(([, value]) => value !== '' && value != null))

const loadUsers = async () => {
  if (!credentials.value) return
  usersLoading.value = true
  try {
    const data = await api.admin.listUsers(credentials.value, cleanQuery({
      q: userQ.value.trim(),
      is_active: userStatus.value,
      page: userPage.value,
      page_size: PAGE_SIZE
    }))
    users.value = data.items
    usersTotal.value = data.total
  } catch (error) {
    toast.add({ title: 'Не удалось загрузить пользователей', description: apiErrorMessage(error), color: 'error' })
  } finally {
    usersLoading.value = false
  }
}
const loadPayments = async () => {
  if (!credentials.value) return
  paymentsLoading.value = true
  try {
    const data = await api.admin.listPayments(credentials.value, cleanQuery({
      q: paymentQ.value.trim(),
      status: paymentStatus.value,
      page: paymentPage.value,
      page_size: PAGE_SIZE
    }))
    payments.value = data.items
    paymentsTotal.value = data.total
  } catch (error) {
    toast.add({ title: 'Не удалось загрузить платежи', description: apiErrorMessage(error), color: 'error' })
  } finally {
    paymentsLoading.value = false
  }
}
const loadWorkflows = async () => {
  if (!credentials.value) return
  workflowsLoading.value = true
  try {
    const data = await api.admin.listWorkflows(credentials.value, cleanQuery({
      q: workflowQ.value.trim(),
      status: workflowStatus.value,
      page: workflowPage.value,
      page_size: PAGE_SIZE
    }))
    workflows.value = data.items
    workflowsTotal.value = data.total
  } catch (error) {
    toast.add({ title: 'Не удалось загрузить цепочки', description: apiErrorMessage(error), color: 'error' })
  } finally {
    workflowsLoading.value = false
  }
}
const loadRuns = async () => {
  if (!credentials.value) return
  runsLoading.value = true
  try {
    const data = await api.admin.listRuns(credentials.value, cleanQuery({
      q: runQ.value.trim(),
      status: runStatus.value,
      page: runPage.value,
      page_size: PAGE_SIZE
    }))
    runs.value = data.items
    runsTotal.value = data.total
  } catch (error) {
    toast.add({ title: 'Не удалось загрузить запуски', description: apiErrorMessage(error), color: 'error' })
  } finally {
    runsLoading.value = false
  }
}

const loaders: Record<string, () => Promise<void>> = {
  users: loadUsers,
  payments: loadPayments,
  workflows: loadWorkflows,
  runs: loadRuns
}

watch([userQ, userStatus], () => { userPage.value = 1 })
watch([paymentQ, paymentStatus], () => { paymentPage.value = 1 })
watch([workflowQ, workflowStatus], () => { workflowPage.value = 1 })
watch([runQ, runStatus], () => { runPage.value = 1 })

const useDelayedLoad = (sources: () => unknown[], loadFn: () => Promise<void>) => {
  let timer: ReturnType<typeof setTimeout> | undefined
  watch(sources, () => {
    clearTimeout(timer)
    timer = setTimeout(() => { void loadFn() }, 280)
  })
}
useDelayedLoad(() => [userQ.value, userStatus.value, userPage.value], loadUsers)
useDelayedLoad(() => [paymentQ.value, paymentStatus.value, paymentPage.value], loadPayments)
useDelayedLoad(() => [workflowQ.value, workflowStatus.value, workflowPage.value], loadWorkflows)
useDelayedLoad(() => [runQ.value, runStatus.value, runPage.value], loadRuns)

watch(tab, (value) => {
  loaders[value]?.()
})

const userColumns: AdminColumn[] = [
  { key: 'id', label: 'ID' },
  { key: 'name', label: 'Имя' },
  { key: 'email', label: 'Email' },
  { key: 'identities', label: 'Входы' },
  { key: 'balance', label: 'Баланс', class: 'text-right' },
  { key: 'is_active', label: 'Статус' },
  { key: 'created_at', label: 'Создан' }
]
const userFields = computed<AdminField[]>(() => [
  { key: 'name', label: 'Имя', type: 'text' },
  { key: 'email', label: 'Email', type: 'text', placeholder: 'name@example.com' },
  { key: 'chat_id', label: 'Telegram chat_id', type: 'number', step: '1' },
  { key: 'balance', label: 'Баланс, токены', type: 'number', step: '0.000001', hint: 'Изменение проходит через ledger, не прямой UPDATE.' },
  { key: 'note', label: 'Комментарий к балансу', type: 'text', placeholder: 'Например: компенсация' },
  {
    key: 'grant_plan_id',
    label: 'Выдать пакет',
    type: 'select',
    hint: 'Записывает покупку без оплаты, начисляет токены пакета и открывает генерацию, распознавание и расшифровку.',
    options: [
      { label: 'Не выдавать', value: 0 },
      ...(config.value?.plans || [])
        .filter(plan => Number(plan.price) > 0)
        .map(plan => ({
          label: `${plan.name} · ${formatCredits(plan.limits?.included_credits)} токенов · ${plan.price} ₽`,
          value: plan.id
        }))
    ]
  },
  { key: 'email_verified', label: 'Email подтверждён', type: 'switch' },
  { key: 'is_active', label: 'Аккаунт включён', type: 'switch' }
])
const userStatusOptions: AdminSelectOption[] = [
  { label: 'Все статусы', value: 'all' },
  { label: 'Активные', value: 'true' },
  { label: 'Отключённые', value: 'false' }
]

const paymentColumns: AdminColumn[] = [
  { key: 'id', label: 'ID' },
  { key: 'user', label: 'Пользователь' },
  { key: 'plan_name', label: 'Тариф' },
  { key: 'amount', label: 'Сумма', class: 'text-right' },
  { key: 'credits', label: 'Credits', class: 'text-right' },
  { key: 'status', label: 'Статус' },
  { key: 'created_at', label: 'Дата' }
]
const paymentFields: AdminField[] = [
  { key: 'amount', label: 'Сумма, ₽', type: 'number', step: '1', hint: 'Правка записи платежа не начисляет токены. Баланс меняйте у пользователя.' },
  { key: 'plan_id', label: 'ID тарифа', type: 'number', step: '1' },
  { key: 'status', label: 'Статус', type: 'select', options: [
    { label: 'Ожидает', value: 'pending' },
    { label: 'Оплачен', value: 'succeeded' },
    { label: 'Ожидает списания', value: 'waiting_for_capture' },
    { label: 'Отменён', value: 'canceled' }
  ] }
]
const paymentStatusOptions: AdminSelectOption[] = [
  { label: 'Все статусы', value: 'all' },
  { label: 'Ожидает', value: 'pending' },
  { label: 'Оплачен', value: 'succeeded' },
  { label: 'Ожидает списания', value: 'waiting_for_capture' },
  { label: 'Отменён', value: 'canceled' }
]

const workflowColumns: AdminColumn[] = [
  { key: 'id', label: 'ID' },
  { key: 'name', label: 'Название' },
  { key: 'owner', label: 'Владелец' },
  { key: 'status', label: 'Статус' },
  { key: 'nodes_count', label: 'Узлы', class: 'text-right' },
  { key: 'schedule', label: 'Расписание' },
  { key: 'updated_at', label: 'Обновлена' }
]
const workflowFields: AdminField[] = [
  { key: 'name', label: 'Название', type: 'text' },
  { key: 'description', label: 'Описание', type: 'textarea' },
  { key: 'status', label: 'Статус', type: 'select', options: [
    { label: 'Черновик', value: 'draft' },
    { label: 'Опубликована', value: 'published' },
    { label: 'Архив', value: 'archived' }
  ] },
  { key: 'schedule_cron', label: 'Cron', type: 'text' },
  { key: 'schedule_timezone', label: 'Часовой пояс', type: 'text' }
]
const workflowStatusOptions: AdminSelectOption[] = [
  { label: 'Все статусы', value: 'all' },
  { label: 'Черновик', value: 'draft' },
  { label: 'Опубликована', value: 'published' },
  { label: 'Архив', value: 'archived' }
]

const runColumns: AdminColumn[] = [
  { key: 'id', label: 'ID' },
  { key: 'workflow_name', label: 'Цепочка' },
  { key: 'owner', label: 'Пользователь' },
  { key: 'status', label: 'Статус' },
  { key: 'cost', label: 'Стоимость', class: 'text-right' },
  { key: 'created_at', label: 'Создан' }
]
const runFields: AdminField[] = [
  { key: 'status', label: 'Статус', type: 'select', options: [
    { label: 'В очереди', value: 'queued' },
    { label: 'Выполняется', value: 'running' },
    { label: 'Готово', value: 'succeeded' },
    { label: 'Ошибка', value: 'failed' },
    { label: 'Отменён', value: 'cancelled' }
  ] },
  { key: 'error', label: 'Ошибка', type: 'textarea' },
  { key: 'cancel_requested', label: 'Запрошена отмена', type: 'switch' }
]
const runStatusOptions: AdminSelectOption[] = [
  { label: 'Все статусы', value: 'all' },
  { label: 'В очереди', value: 'queued' },
  { label: 'Выполняется', value: 'running' },
  { label: 'Готово', value: 'succeeded' },
  { label: 'Ошибка', value: 'failed' },
  { label: 'Отменён', value: 'cancelled' }
]

const saveUser = async (row: AdminUserRecord, form: Record<string, unknown>) => {
  usersSaving.value = true
  try {
    const updated = await api.admin.updateUser(credentials.value, row.id, form)
    users.value = users.value.map(item => item.id === updated.id ? { ...item, ...updated } : item)
    editingUser.value = updated
    toast.add({ title: 'Пользователь сохранён', color: 'success' })
    return true
  } catch (error) {
    toast.add({ title: 'Не удалось сохранить', description: apiErrorMessage(error), color: 'error' })
    return false
  } finally {
    usersSaving.value = false
  }
}
const removeUser = async (row: AdminUserRecord) => {
  usersDeleting.value = true
  try {
    await api.admin.deleteUser(credentials.value, row.id)
    toast.add({ title: 'Пользователь удалён', color: 'success' })
    await loadUsers()
    return true
  } catch (error) {
    toast.add({ title: 'Не удалось удалить', description: apiErrorMessage(error), color: 'error' })
    return false
  } finally {
    usersDeleting.value = false
  }
}
const loginAsUser = async (row: AdminUserRecord) => {
  if (!row.is_active) {
    toast.add({ title: 'Аккаунт отключён', description: 'Включите пользователя, чтобы войти под ним.', color: 'warning' })
    return
  }
  impersonatingId.value = row.id
  try {
    await auth.accept(await api.admin.loginAsUser(credentials.value, row.id))
    toast.add({ title: `Вы вошли как ${row.name}`, color: 'success' })
    await navigateTo('/dashboard')
  } catch (error) {
    toast.add({ title: 'Не удалось войти', description: apiErrorMessage(error), color: 'error' })
  } finally {
    impersonatingId.value = undefined
  }
}
const savePayment = async (row: AdminPaymentRecord, form: Record<string, unknown>) => {
  paymentsSaving.value = true
  try {
    const updated = await api.admin.updatePayment(credentials.value, row.id, form)
    payments.value = payments.value.map(item => item.id === updated.id ? updated : item)
    toast.add({ title: 'Платёж сохранён', color: 'success' })
    return true
  } catch (error) {
    toast.add({ title: 'Не удалось сохранить', description: apiErrorMessage(error), color: 'error' })
    return false
  } finally {
    paymentsSaving.value = false
  }
}
const removePayment = async (row: AdminPaymentRecord) => {
  paymentsDeleting.value = true
  try {
    await api.admin.deletePayment(credentials.value, row.id)
    toast.add({ title: 'Платёж удалён', color: 'success' })
    await loadPayments()
    return true
  } catch (error) {
    toast.add({ title: 'Не удалось удалить', description: apiErrorMessage(error), color: 'error' })
    return false
  } finally {
    paymentsDeleting.value = false
  }
}
const saveWorkflow = async (row: AdminWorkflowRecord, form: Record<string, unknown>) => {
  workflowsSaving.value = true
  try {
    const updated = await api.admin.updateWorkflow(credentials.value, row.id, form)
    workflows.value = workflows.value.map(item => item.id === updated.id ? updated : item)
    toast.add({ title: 'Цепочка сохранена', color: 'success' })
    return true
  } catch (error) {
    toast.add({ title: 'Не удалось сохранить', description: apiErrorMessage(error), color: 'error' })
    return false
  } finally {
    workflowsSaving.value = false
  }
}
const removeWorkflow = async (row: AdminWorkflowRecord) => {
  workflowsDeleting.value = true
  try {
    await api.admin.deleteWorkflow(credentials.value, row.id)
    toast.add({ title: 'Цепочка удалена', color: 'success' })
    await loadWorkflows()
    return true
  } catch (error) {
    toast.add({ title: 'Не удалось удалить', description: apiErrorMessage(error), color: 'error' })
    return false
  } finally {
    workflowsDeleting.value = false
  }
}
const saveRun = async (row: AdminRunRecord, form: Record<string, unknown>) => {
  runsSaving.value = true
  try {
    const updated = await api.admin.updateRun(credentials.value, row.id, form)
    runs.value = runs.value.map(item => item.id === updated.id ? updated : item)
    toast.add({ title: 'Запуск сохранён', color: 'success' })
    return true
  } catch (error) {
    toast.add({ title: 'Не удалось сохранить', description: apiErrorMessage(error), color: 'error' })
    return false
  } finally {
    runsSaving.value = false
  }
}
const removeRun = async (row: AdminRunRecord) => {
  runsDeleting.value = true
  try {
    await api.admin.deleteRun(credentials.value, row.id)
    toast.add({ title: 'Запуск удалён', color: 'success' })
    await loadRuns()
    return true
  } catch (error) {
    toast.add({ title: 'Не удалось удалить', description: apiErrorMessage(error), color: 'error' })
    return false
  } finally {
    runsDeleting.value = false
  }
}

const onOpenUser = async (row: AdminUserRecord) => {
  try {
    editingUser.value = await api.admin.getUser(credentials.value, row.id)
  } catch {
    editingUser.value = row
  }
}

onMounted(() => {
  const fromSession = (() => {
    try { return sessionStorage.getItem(ADMIN_AUTH_KEY) } catch { return null }
  })()
  if (fromSession) {
    writeLocal(ADMIN_AUTH_KEY, fromSession)
    try { sessionStorage.removeItem(ADMIN_AUTH_KEY) } catch { /* ignore */ }
  }
  credentials.value = readLocal(ADMIN_AUTH_KEY) || ''
  if (credentials.value) load()
})

watch(credentials, (value) => {
  if (value) loadUsers()
})
</script>

<template>
  <UApp>
    <main class="admin-page">
      <div class="shell admin-shell">
        <div v-if="!config" class="admin-login panel">
          <p class="eyebrow">Ayakun Admin</p>
          <h1 class="page-title" style="font-size: 34px">Вход в панель</h1>
          <form class="space-y-4" @submit.prevent="signIn">
            <UFormField label="Логин">
              <UInput v-model="login" autocomplete="username" class="w-full" />
            </UFormField>
            <UFormField label="Пароль">
              <UInput v-model="password" type="password" autocomplete="current-password" class="w-full" />
            </UFormField>
            <UButton type="submit" label="Войти" block size="lg" :loading="loading" />
          </form>
        </div>

        <template v-else>
          <header class="page-head">
            <div>
              <p class="eyebrow">Ayakun Admin</p>
              <h1 class="page-title">Данные и настройки</h1>
              <p class="muted">Пользователи, платежи, цепочки и запуски — с правкой баланса через ledger.</p>
            </div>
            <UButton label="Выйти" color="neutral" variant="soft" @click="signOut" />
          </header>

          <UTabs v-model="tab" :items="tabs" variant="pill" class="admin-tabs" :unmount-on-hide="false">
            <template #users>
              <div class="panel admin-panel">
                <AdminRecordsTab
                  v-model:q="userQ"
                  v-model:status="userStatus"
                  v-model:page="userPage"
                  title="Пользователи"
                  search-placeholder="Имя, email, ID или chat_id"
                  :status-options="userStatusOptions"
                  :columns="userColumns"
                  :fields="userFields"
                  :items="users"
                  :total="usersTotal"
                  :page-size="PAGE_SIZE"
                  :loading="usersLoading"
                  :saving="usersSaving"
                  :deleting="usersDeleting"
                  edit-title="Пользователь"
                  delete-title="Удалить пользователя"
                  :delete-text="(row) => `Удалить «${row.name}» и все связанные данные: цепочки, платежи, токены?`"
                  @open="onOpenUser"
                  :on-save="saveUser"
                  :on-remove="removeUser"
                >
                  <template #actions="{ row }">
                    <UButton
                      icon="i-lucide-log-in"
                      color="neutral"
                      variant="soft"
                      size="sm"
                      :disabled="!row.is_active"
                      :loading="impersonatingId === row.id"
                      aria-label="Войти как пользователь"
                      :title="row.is_active ? 'Войти как этот пользователь' : 'Аккаунт отключён'"
                      @click="loginAsUser(row)"
                    />
                  </template>
                  <template #id="{ row, copy }">
                    <button type="button" class="admin-id" :title="String(row.id)" @click="copy(row.id)">{{ row.id }}</button>
                  </template>
                  <template #name="{ row }">
                    <div>
                      <p class="admin-primary">{{ row.name }}</p>
                      <p v-if="row.chat_id" class="admin-meta">Telegram {{ row.chat_id }}</p>
                    </div>
                  </template>
                  <template #email="{ row }">{{ row.email || '—' }}</template>
                  <template #identities="{ row }">
                    <div class="admin-chips">
                      <UBadge v-for="item in row.identities" :key="item.provider + item.subject" variant="soft" color="neutral">
                        {{ identityLabel(item.provider) }}
                      </UBadge>
                      <span v-if="!row.identities.length" class="muted">—</span>
                    </div>
                  </template>
                  <template #balance="{ row }">
                    <div class="text-right">
                      <p class="admin-primary tabular-nums">{{ formatCredits(row.balance) }}</p>
                      <p v-if="row.reserved" class="admin-meta">резерв {{ formatCredits(row.reserved) }}</p>
                    </div>
                  </template>
                  <template #is_active="{ row }">
                    <UBadge :color="row.is_active ? 'success' : 'neutral'" variant="soft">
                      {{ row.is_active ? 'Активен' : 'Отключён' }}
                    </UBadge>
                  </template>
                  <template #created_at="{ row }">{{ formatDate(row.created_at) }}</template>
                  <template #edit-extra="{ row }">
                    <UButton
                      v-if="row"
                      label="Войти как этот пользователь"
                      icon="i-lucide-log-in"
                      color="neutral"
                      variant="soft"
                      block
                      :disabled="!row.is_active"
                      :loading="impersonatingId === row.id"
                      @click="loginAsUser(row)"
                    />
                    <div v-if="(editingUser?.id === row?.id ? editingUser : row)?.ledger?.length" class="admin-ledger">
                      <p class="admin-ledger-title">Последние операции баланса</p>
                      <div v-for="entry in (editingUser?.id === row?.id ? editingUser?.ledger : row?.ledger) || []" :key="entry.id" class="admin-ledger-row">
                        <div>
                          <p class="admin-primary">{{ ledgerDescription({ ...entry, metadata_: entry.metadata }) }}</p>
                          <p class="admin-meta">{{ formatDate(entry.created_at) }}</p>
                        </div>
                        <strong :class="entry.amount >= 0 ? 'text-[#4b3dcc]' : 'text-[#c45c3e]'">
                          {{ entry.amount > 0 ? '+' : '' }}{{ formatCredits(entry.amount) }}
                        </strong>
                      </div>
                    </div>
                  </template>
                </AdminRecordsTab>
              </div>
            </template>

            <template #payments>
              <div class="panel admin-panel">
                <AdminRecordsTab
                  v-model:q="paymentQ"
                  v-model:status="paymentStatus"
                  v-model:page="paymentPage"
                  search-placeholder="Пользователь, ID платежа или провайдер"
                  :status-options="paymentStatusOptions"
                  :columns="paymentColumns"
                  :fields="paymentFields"
                  :items="payments"
                  :total="paymentsTotal"
                  :page-size="PAGE_SIZE"
                  :loading="paymentsLoading"
                  :saving="paymentsSaving"
                  :deleting="paymentsDeleting"
                  edit-title="Платёж"
                  delete-title="Удалить платёж"
                  :delete-text="(row) => `Удалить платёж ${shortId(row.id)}? Credits на балансе не изменятся.`"
                  :on-save="savePayment"
                  :on-remove="removePayment"
                >
                  <template #id="{ row, copy }">
                    <button type="button" class="admin-id" :title="row.id" @click="copy(row.id)">{{ shortId(row.id) }}</button>
                  </template>
                  <template #user="{ row }">
                    <div>
                      <p class="admin-primary">{{ row.user_name || `ID ${row.user_id}` }}</p>
                      <p class="admin-meta">{{ row.user_email || `user #${row.user_id}` }}</p>
                    </div>
                  </template>
                  <template #plan_name="{ row }">{{ row.plan_name || '—' }}</template>
                  <template #amount="{ row }">
                    <span class="tabular-nums">{{ Number(row.amount).toLocaleString('ru-RU') }} ₽</span>
                  </template>
                  <template #credits="{ row }">
                    <span class="tabular-nums">{{ row.credits == null ? '—' : formatCredits(row.credits) }}</span>
                  </template>
                  <template #status="{ row }">
                    <UBadge :color="paymentStatusColor(row.status)" variant="soft">{{ paymentStatusLabel(row.status) }}</UBadge>
                  </template>
                  <template #created_at="{ row }">{{ formatDate(row.created_at) }}</template>
                </AdminRecordsTab>
              </div>
            </template>

            <template #workflows>
              <div class="panel admin-panel">
                <AdminRecordsTab
                  v-model:q="workflowQ"
                  v-model:status="workflowStatus"
                  v-model:page="workflowPage"
                  search-placeholder="Название, владелец или ID"
                  :status-options="workflowStatusOptions"
                  :columns="workflowColumns"
                  :fields="workflowFields"
                  :items="workflows"
                  :total="workflowsTotal"
                  :page-size="PAGE_SIZE"
                  :loading="workflowsLoading"
                  :saving="workflowsSaving"
                  :deleting="workflowsDeleting"
                  edit-title="Цепочка"
                  delete-title="Удалить цепочку"
                  :delete-text="(row) => `Удалить цепочку «${row.name}» и её запуски?`"
                  :on-save="saveWorkflow"
                  :on-remove="removeWorkflow"
                >
                  <template #id="{ row, copy }">
                    <button type="button" class="admin-id" :title="row.id" @click="copy(row.id)">{{ shortId(row.id) }}</button>
                  </template>
                  <template #name="{ row }">
                    <p class="admin-primary">{{ row.name }}</p>
                    <p v-if="row.description" class="admin-meta">{{ row.description }}</p>
                  </template>
                  <template #owner="{ row }">
                    <div>
                      <p class="admin-primary">{{ row.owner_name || `ID ${row.owner_id}` }}</p>
                      <p class="admin-meta">{{ row.owner_email || `user #${row.owner_id}` }}</p>
                    </div>
                  </template>
                  <template #status="{ row }">
                    <UBadge :color="workflowStatusColor(row.status)" variant="soft">{{ workflowStatusLabel(row.status) }}</UBadge>
                  </template>
                  <template #nodes_count="{ row }">{{ row.nodes_count }}</template>
                  <template #schedule="{ row }">{{ row.schedule_cron || '—' }}</template>
                  <template #updated_at="{ row }">{{ formatDate(row.updated_at) }}</template>
                </AdminRecordsTab>
              </div>
            </template>

            <template #runs>
              <div class="panel admin-panel">
                <AdminRecordsTab
                  v-model:q="runQ"
                  v-model:status="runStatus"
                  v-model:page="runPage"
                  search-placeholder="Цепочка, пользователь, ошибка или ID"
                  :status-options="runStatusOptions"
                  :columns="runColumns"
                  :fields="runFields"
                  :items="runs"
                  :total="runsTotal"
                  :page-size="PAGE_SIZE"
                  :loading="runsLoading"
                  :saving="runsSaving"
                  :deleting="runsDeleting"
                  edit-title="Запуск"
                  delete-title="Удалить запуск"
                  :delete-text="(row) => `Удалить запуск ${shortId(row.id)}?`"
                  :on-save="saveRun"
                  :on-remove="removeRun"
                >
                  <template #id="{ row, copy }">
                    <button type="button" class="admin-id" :title="row.id" @click="copy(row.id)">{{ shortId(row.id) }}</button>
                  </template>
                  <template #workflow_name="{ row }">{{ row.workflow_name || shortId(row.workflow_id) }}</template>
                  <template #owner="{ row }">
                    <div>
                      <p class="admin-primary">{{ row.owner_name || `ID ${row.owner_id}` }}</p>
                      <p class="admin-meta">{{ row.owner_email || `user #${row.owner_id}` }}</p>
                    </div>
                  </template>
                  <template #status="{ row }">
                    <UBadge :color="statusColor(row.status)" variant="soft">{{ statusLabel(row.status) }}</UBadge>
                  </template>
                  <template #cost="{ row }">
                    <span class="tabular-nums">{{ formatCredits(row.cost) }}</span>
                  </template>
                  <template #created_at="{ row }">{{ formatDate(row.created_at) }}</template>
                </AdminRecordsTab>
              </div>
            </template>

            <template #settings>
              <div class="pt-2">
                <h2 class="admin-section-title">Настройки выполнения</h2>
                <div class="mb-9 grid gap-3 md:grid-cols-2">
                  <article v-for="setting in config.settings" :key="setting.key" class="panel admin-card">
                    <p class="admin-card-title">{{ setting.description }}</p>
                    <p class="admin-card-meta">{{ setting.key }}</p>
                    <div class="flex gap-2">
                      <USelect
                        v-if="setting.key === 'vision_provider'"
                        :model-value="String(setting.value)"
                        :items="VISION_PROVIDERS"
                        value-key="value"
                        class="flex-1"
                        @update:model-value="setting.value = String($event ?? '')"
                      />
                      <UInput
                        v-else-if="isCreditSetting(setting.key)"
                        :model-value="String(setting.value)"
                        type="number"
                        min="0"
                        step="0.001"
                        class="flex-1"
                        @update:model-value="setting.value = $event === '' ? 0 : Number($event)"
                      />
                      <UInput
                        v-else
                        :model-value="String(setting.value)"
                        class="flex-1"
                        @update:model-value="setting.value = String($event)"
                      />
                      <UButton label="Сохранить" variant="soft" @click="saveSetting(setting)" />
                    </div>
                  </article>
                </div>

                <h2 class="admin-section-title">Поиск</h2>
                <div class="mb-9 grid gap-4 lg:grid-cols-2">
                  <article v-for="rate in searchRates" :key="rate.id" class="panel admin-card">
                    <div class="mb-5 flex items-center justify-between">
                      <div>
                        <strong class="admin-card-title">{{ rate.model }}</strong>
                        <p class="admin-card-meta mb-0">{{ rate.provider }}</p>
                      </div>
                      <USwitch v-model="rate.active" />
                    </div>
                    <UFormField label="Стоимость одного поиска в токенах">
                      <UInput v-model="rate.search_credits" type="number" step="0.001" class="w-full" />
                    </UFormField>
                    <UButton class="mt-5" label="Сохранить" variant="soft" @click="saveSearchRate(rate)" />
                  </article>
                </div>

                <h2 class="admin-section-title">Тарифы</h2>
                <div class="grid gap-4 lg:grid-cols-2">
                  <article v-for="plan in config.plans" :key="plan.id" class="panel admin-card">
                    <div class="grid gap-3 sm:grid-cols-2">
                      <UFormField label="Название"><UInput v-model="plan.name" class="w-full" /></UFormField>
                      <UFormField label="Цена"><UInput v-model="plan.price" type="number" step="1" class="w-full" /></UFormField>
                      <UFormField label="Токенов в пакете"><UInput v-model="plan.limits.included_credits" type="number" class="w-full" /></UFormField>
                      <UFormField label="Лимит одного запуска"><UInput v-model="plan.limits.run_cap_credits" type="number" class="w-full" /></UFormField>
                      <UFormField label="Валюта"><UInput v-model="plan.currency" maxlength="3" class="w-full" /></UFormField>
                    </div>
                    <UButton class="mt-5" label="Сохранить тариф" variant="soft" @click="savePlan(plan)" />
                  </article>
                </div>
              </div>
            </template>
          </UTabs>
        </template>
      </div>
    </main>
  </UApp>
</template>
