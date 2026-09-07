<template>
  <main>
    <section class="page grid min-h-[70vh] place-items-center text-center">
      <div class="max-w-3xl">
        <UBadge label="Визуальные AI-автоматизации" variant="soft" size="lg" />
        <h1 class="mt-6 text-5xl font-bold tracking-tight md:text-7xl">Соберите AI-цепочку.<br><span class="text-primary">Без кода.</span></h1>
        <p class="mx-auto mt-6 max-w-2xl text-lg muted">Поиск в интернете, обработка через Qwen и DeepSeek, доставка результата в Telegram — на одном наглядном canvas.</p>
        <div class="mt-8 flex justify-center gap-3">
          <UButton to="/auth" size="xl" label="Начать бесплатно" trailing-icon="i-lucide-arrow-right" />
          <UButton to="/pricing" size="xl" label="Тарифы" color="neutral" variant="outline" />
        </div>
      </div>
    </section>
    <section id="features" class="page grid-cards">
      <UCard v-for="item in [
        { icon: 'i-lucide-mouse-pointer-2', title: 'Визуальный редактор', text: 'Соединяйте готовые узлы перетаскиванием.' },
        { icon: 'i-lucide-search', title: 'Актуальный поиск', text: 'Qwen ищет источники и сохраняет ссылки.' },
        { icon: 'i-lucide-send', title: 'Доставка в Telegram', text: 'Результат приходит туда, где вы уже работаете.' }
      ]" :key="item.title">
        <UIcon :name="item.icon" class="size-8 text-primary" />
        <h2 class="mt-4 text-xl font-semibold">{{ item.title }}</h2>
        <p class="mt-2 muted">{{ item.text }}</p>
      </UCard>
    </section>
  </main>
</template>
