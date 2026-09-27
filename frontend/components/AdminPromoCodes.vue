<script setup lang="ts">
import type { Plan, PromoCode } from '~/types/api'
import { apiErrorMessage } from '~/composables/useApi'

const props = defineProps<{ credentials: string; plans: Plan[] }>()

const api = useApi()
const toast = useToast()

const items = ref<PromoCode[]>([])
const loading = ref(false)
const saving = ref(false)
const deleting = ref(false)
const q = ref('')

const load = async () => {
  loading.value = true
  try {
    items.value = await api.admin.listPromoCodes(props.credentials)
  } catch (error) {
    toast.add({ title: 'Не удалось загрузить промокоды', description: apiErrorMessage(error), color: 'error' })
  } finally {
    loading.value = false
  }
}
onMounted(load)

const paidPlans = computed(() => props.plans.filter(plan => Number(plan.price) > 0))
const filtered = computed(() => {
  const query = q.value.trim().toLowerCase()
  if (!query) return items.value
  return items.value.filter(item => item.code.toLowerCase().includes(query))
})

const planName = (id: number) => props.plans.find(plan => plan.id === id)?.name || `ID ${id}`
const planLabel = (item: PromoCode) => (item.plan_ids?.length ? item.plan_ids.map(planName).join(', ') : 'Все тарифы')
const isExpired = (item: PromoCode) => Boolean(item.expires_at && new Date(item.expires_at).getTime() < Date.now())

const formatDate = (value?: string | null, withTime = false) => {
  if (!value) return '—'
  return new Date(value).toLocaleString('ru', withTime
    ? { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }
    : { day: '2-digit', month: 'short', year: 'numeric' })
}
const toDateInputValue = (iso: string) => new Date(iso).toISOString().slice(0, 10)

type PromoForm = { discount_percent: number; plan_ids: number[]; expires_at: string; active: boolean }
const togglePlan = (form: PromoForm, id: number) => {
  const index = form.plan_ids.indexOf(id)
  if (index >= 0) form.plan_ids.splice(index, 1)
  else form.plan_ids.push(id)
}

const createOpen = ref(false)
const createForm = reactive<PromoForm & { code: string }>({ code: '', discount_percent: 10, plan_ids: [], expires_at: '', active: true })
const openCreate = () => {
  createForm.code = ''
  createForm.discount_percent = 10
  createForm.plan_ids = []
  createForm.expires_at = ''
  createForm.active = true
  createOpen.value = true
}
const submitCreate = async () => {
  const code = createForm.code.trim().toUpperCase()
  if (!code) {
    toast.add({ title: 'Укажите код промокода', color: 'error' })
    return
  }
  saving.value = true
  try {
    const created = await api.admin.createPromoCode(props.credentials, {
      code,
      discount_percent: Number(createForm.discount_percent),
      plan_ids: createForm.plan_ids.length ? [...createForm.plan_ids] : null,
      expires_at: createForm.expires_at ? new Date(createForm.expires_at).toISOString() : null,
      active: createForm.active
    })
    items.value = [created, ...items.value]
    toast.add({ title: 'Промокод создан', color: 'success' })
    createOpen.value = false
  } catch (error) {
    toast.add({ title: 'Не удалось создать промокод', description: apiErrorMessage(error), color: 'error' })
  } finally {
    saving.value = false
  }
}

const editOpen = ref(false)
const editing = ref<PromoCode | null>(null)
const editForm = reactive<PromoForm>({ discount_percent: 10, plan_ids: [], expires_at: '', active: true })
const openEdit = (item: PromoCode) => {
  editing.value = item
  editForm.discount_percent = item.discount_percent
  editForm.plan_ids = item.plan_ids ? [...item.plan_ids] : []
  editForm.expires_at = item.expires_at ? toDateInputValue(item.expires_at) : ''
  editForm.active = item.active
  editOpen.value = true
}
const submitEdit = async () => {
  if (!editing.value) return
  saving.value = true
  try {
    const updated = await api.admin.updatePromoCode(props.credentials, editing.value.id, {
      discount_percent: Number(editForm.discount_percent),
      plan_ids: editForm.plan_ids.length ? [...editForm.plan_ids] : null,
      expires_at: editForm.expires_at ? new Date(editForm.expires_at).toISOString() : null,
      active: editForm.active
    })
    items.value = items.value.map(item => (item.id === updated.id ? updated : item))
    toast.add({ title: 'Промокод сохранён', color: 'success' })
    editOpen.value = false
  } catch (error) {
    toast.add({ title: 'Не удалось сохранить', description: apiErrorMessage(error), color: 'error' })
  } finally {
    saving.value = false
  }
}

const deleteOpen = ref(false)
const deletingItem = ref<PromoCode | null>(null)
const openDelete = (item: PromoCode) => {
  deletingItem.value = item
  deleteOpen.value = true
}
const confirmDelete = async () => {
  const item = deletingItem.value
  if (!item) return
  deleting.value = true
  try {
    await api.admin.deletePromoCode(props.credentials, item.id)
    items.value = items.value.filter(row => row.id !== item.id)
    toast.add({ title: 'Промокод удалён', color: 'success' })
    deleteOpen.value = false
  } catch (error) {
    toast.add({ title: 'Не удалось удалить', description: apiErrorMessage(error), color: 'error' })
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <div class="panel admin-panel">
    <div class="admin-records">
      <div class="admin-toolbar">
        <UInput v-model="q" placeholder="Поиск по коду" icon="i-lucide-search" class="admin-search" />
        <p class="admin-range">{{ items.length }} промокодов</p>
        <UButton label="Создать промокод" icon="i-lucide-plus" @click="openCreate" />
      </div>

      <div class="admin-table-wrap">
        <div v-if="loading" class="admin-table-loading">
          <USkeleton v-for="i in 4" :key="i" class="h-12" />
        </div>
        <table v-else class="admin-table">
          <thead>
            <tr>
              <th>Код</th>
              <th>Скидка</th>
              <th>Тарифы</th>
              <th>Истекает</th>
              <th>Статус</th>
              <th class="text-right">Использований</th>
              <th>Создан</th>
              <th class="admin-col-actions">Действия</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="!filtered.length">
              <td colspan="8" class="admin-empty">Промокодов пока нет</td>
            </tr>
            <tr v-for="item in filtered" :key="item.id">
              <td><span class="admin-primary font-mono">{{ item.code }}</span></td>
              <td><UBadge color="success" variant="soft">−{{ item.discount_percent }}%</UBadge></td>
              <td class="admin-meta">{{ planLabel(item) }}</td>
              <td :class="{ 'text-[#c2410c]': isExpired(item) }">{{ formatDate(item.expires_at) }}</td>
              <td>
                <UBadge v-if="isExpired(item)" color="warning" variant="soft">Истёк</UBadge>
                <UBadge v-else :color="item.active ? 'success' : 'neutral'" variant="soft">{{ item.active ? 'Активен' : 'Выключен' }}</UBadge>
              </td>
              <td class="text-right tabular-nums admin-primary">{{ item.usage_count }}</td>
              <td class="admin-meta">{{ formatDate(item.created_at, true) }}</td>
              <td class="admin-col-actions">
                <div class="admin-row-actions">
                  <UButton icon="i-lucide-pencil" color="neutral" variant="soft" size="sm" aria-label="Изменить" @click="openEdit(item)" />
                  <UButton icon="i-lucide-trash-2" color="error" variant="soft" size="sm" aria-label="Удалить" @click="openDelete(item)" />
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <UModal
        :open="createOpen"
        title="Новый промокод"
        :ui="{ footer: 'justify-end', content: 'bg-white!', header: '[&_h2]:text-white!' }"
        @update:open="createOpen = $event"
      >
        <template #body>
          <form class="admin-edit-form" @submit.prevent="submitCreate">
            <UFormField label="Код">
              <UInput v-model="createForm.code" class="w-full font-mono uppercase" placeholder="LETO2026" maxlength="40" autofocus />
            </UFormField>
            <UFormField label="Скидка, %">
              <UInput v-model="createForm.discount_percent" type="number" min="1" max="100" class="w-full" />
            </UFormField>
            <UFormField label="Тарифы, на которые распространяется">
              <div class="promo-plan-list">
                <label v-for="plan in paidPlans" :key="plan.id" class="flex items-center gap-2 text-[13px] font-semibold">
                  <UCheckbox :model-value="createForm.plan_ids.includes(plan.id)" @update:model-value="togglePlan(createForm, plan.id)" />
                  {{ plan.name }}
                </label>
                <p class="admin-meta mb-0">Ничего не выбрано — код действует на все платные тарифы.</p>
              </div>
            </UFormField>
            <UFormField label="Действует до" hint="Пусто — бессрочно">
              <UInput v-model="createForm.expires_at" type="date" class="w-full" />
            </UFormField>
            <label class="flex items-center gap-2 text-[13px] font-semibold">
              <USwitch v-model="createForm.active" />
              Активен
            </label>
          </form>
        </template>
        <template #footer="{ close }">
          <UButton label="Отмена" color="neutral" variant="outline" :disabled="saving" @click="close" />
          <UButton label="Создать" :loading="saving" @click="submitCreate" />
        </template>
      </UModal>

      <UModal
        :open="editOpen"
        title="Промокод"
        :ui="{ footer: 'justify-end', content: 'bg-white!', header: '[&_h2]:text-white!' }"
        @update:open="editOpen = $event"
      >
        <template #body>
          <form class="admin-edit-form" @submit.prevent="submitEdit">
            <UFormField label="Код">
              <UInput :model-value="editing?.code" class="w-full font-mono uppercase" disabled />
            </UFormField>
            <UFormField label="Скидка, %">
              <UInput v-model="editForm.discount_percent" type="number" min="1" max="100" class="w-full" />
            </UFormField>
            <UFormField label="Тарифы, на которые распространяется">
              <div class="promo-plan-list">
                <label v-for="plan in paidPlans" :key="plan.id" class="flex items-center gap-2 text-[13px] font-semibold">
                  <UCheckbox :model-value="editForm.plan_ids.includes(plan.id)" @update:model-value="togglePlan(editForm, plan.id)" />
                  {{ plan.name }}
                </label>
                <p class="admin-meta mb-0">Ничего не выбрано — код действует на все платные тарифы.</p>
              </div>
            </UFormField>
            <UFormField label="Действует до" hint="Пусто — бессрочно">
              <UInput v-model="editForm.expires_at" type="date" class="w-full" />
            </UFormField>
            <label class="flex items-center gap-2 text-[13px] font-semibold">
              <USwitch v-model="editForm.active" />
              Активен
            </label>
            <p v-if="editing" class="admin-meta mb-0">Использован раз: {{ editing.usage_count }}</p>
          </form>
        </template>
        <template #footer="{ close }">
          <UButton label="Отмена" color="neutral" variant="outline" :disabled="saving" @click="close" />
          <UButton label="Сохранить" :loading="saving" @click="submitEdit" />
        </template>
      </UModal>

      <UModal
        :open="deleteOpen"
        title="Удалить промокод"
        :ui="{ footer: 'justify-end', content: 'bg-white!', header: '[&_h2]:text-white!' }"
        @update:open="deleteOpen = $event"
      >
        <template #body>
          <p class="mb-0 text-[15px] leading-6">
            Удалить промокод «{{ deletingItem?.code }}»? Это действие нельзя отменить.
          </p>
        </template>
        <template #footer="{ close }">
          <UButton label="Отмена" color="neutral" variant="outline" :disabled="deleting" @click="close" />
          <UButton label="Удалить" color="error" :loading="deleting" @click="confirmDelete" />
        </template>
      </UModal>
    </div>
  </div>
</template>

<style scoped>
.promo-plan-list {
  display: grid;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 10px;
}
</style>
