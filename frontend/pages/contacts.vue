<script setup lang="ts">
import { LEGAL } from '~/utils/legal'

useSeoMeta({
  title: 'Контакты и реквизиты',
  description: 'Контакты и реквизиты ИП для сервиса Ayakun'
})
</script>

<template>
  <main class="shell legal-page">
    <div class="legal-card reveal">
      <p class="eyebrow">Связь и реквизиты</p>
      <h1 class="page-title">Контакты</h1>
      <p class="legal-meta muted">Как связаться с исполнителем и куда писать по оплате и договору.</p>

      <div class="legal-body">
        <div class="requisites">
          <div>
            <p class="mb-1 text-xs font-extrabold uppercase tracking-wider muted">Исполнитель</p>
            <p class="mb-0 font-extrabold">{{ LEGAL.entity }}</p>
          </div>
          <div>
            <p class="mb-1 text-xs font-extrabold uppercase tracking-wider muted">Телефон</p>
            <a :href="`tel:${LEGAL.phone}`" class="legal-link">{{ LEGAL.phoneDisplay }}</a>
          </div>
          <div>
            <p class="mb-1 text-xs font-extrabold uppercase tracking-wider muted">Электронная почта</p>
            <a :href="`mailto:${LEGAL.email}`" class="legal-link">{{ LEGAL.email }}</a>
          </div>
          <div>
            <p class="mb-1 text-xs font-extrabold uppercase tracking-wider muted">Почтовый адрес</p>
            <p class="mb-0">{{ LEGAL.address }}</p>
          </div>
          <div>
            <p class="mb-1 text-xs font-extrabold uppercase tracking-wider muted">ИНН</p>
            <p class="mb-0">{{ LEGAL.inn }}</p>
          </div>
          <div>
            <p class="mb-1 text-xs font-extrabold uppercase tracking-wider muted">ОГРНИП</p>
            <p class="mb-0">{{ LEGAL.ogrnip }}</p>
          </div>
        </div>

        <h2>По каким вопросам писать</h2>
        <p>По доступу к кабинету, списанию кредитов, оплате тарифа и оферте — на почту или по телефону в рабочие часы.</p>
      </div>

      <div class="legal-actions">
        <NuxtLink to="/terms" class="site-button secondary">Публичная оферта</NuxtLink>
        <NuxtLink to="/privacy" class="site-button secondary">Конфиденциальность</NuxtLink>
        <NuxtLink to="/delivery" class="site-button secondary">Как получить услугу</NuxtLink>
      </div>
    </div>
  </main>
</template>
