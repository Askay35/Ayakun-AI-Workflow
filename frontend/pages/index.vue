<template>
  <main>
    <section class="hero">
      <div class="shell hero-grid">
        <div class="reveal">
          <p class="eyebrow">Визуальные AI-цепочки</p>
          <h1>Автоматизация,<br><span class="hero-shine">которую видно</span></h1>
          <p class="hero-copy">
            Ayakun собирает поиск, анализ и доставку в одну цепочку.
            Вы описываете задачу обычными словами — сервис сам находит данные,
            обрабатывает их и присылает результат в Telegram.
          </p>
          <div class="hero-actions">
            <UButton to="/login" size="xl" label="Начать бесплатно" trailing-icon="i-lucide-arrow-right" />
            <UButton to="/#how" size="xl" label="Как это работает" class="text-white!" color="neutral" variant="outline" />
          </div>
          <div class="trust-row">
            <span><UIcon name="i-lucide-check-circle-2" /> Без кода и серверов</span>
            <span><UIcon name="i-lucide-check-circle-2" /> Гибкие тарифы</span>
            <span><UIcon name="i-lucide-check-circle-2" /> 1000 credits при регистрации</span>
          </div>
        </div>
        <LandingCanvas class="reveal" style="animation-delay: 140ms" />
      </div>
    </section>

    <section class="unique-strip">
      <div class="shell unique-grid">
        <article v-for="(item, index) in unique" :key="item.title" class="unique-card" :style="{ animationDelay: `${index * 80}ms` }">
          <span class="unique-icon"><UIcon :name="item.icon" class="size-5" /></span>
          <h3>{{ item.title }}</h3>
          <p>{{ item.text }}</p>
        </article>
      </div>
    </section>

    <section id="features" class="section alt">
      <div class="shell">
        <div class="section-heading">
          <p class="eyebrow">Что делает Ayakun</p>
          <h2>От запроса до готового ответа — без ручной работы</h2>
          <p>Одна цепочка заменяет вкладки, копирование и ежедневные проверки. Настроили один раз — дальше сервис работает сам.</p>
        </div>
        <div class="feature-grid">
          <article v-for="(card, index) in features" :key="card.title" class="feature-card">
            <span class="feature-number">{{ card.number }}</span>
            <span class="feature-icon" :style="{ color: card.accent, background: `${card.accent}22` }">
              <UIcon :name="card.icon" class="size-5" />
            </span>
            <h3>{{ card.title }}</h3>
            <p>{{ card.text }}</p>
            <span v-if="index < features.length - 1" class="feature-flow" />
          </article>
        </div>
      </div>
    </section>

    <section id="how" class="section">
      <div class="shell">
        <div class="section-heading">
          <p class="eyebrow">Три шага</p>
          <h2>Первая цепочка — за несколько минут</h2>
        </div>
        <div class="build-track">
          <article v-for="(step, index) in steps" :key="step.title" class="build-step">
            <div class="build-visual" :class="`is-${step.id}`">
              <span v-for="dot in 3" :key="dot" class="build-chip" :style="{ animationDelay: `${index * 180 + dot * 90}ms` }">
                <UIcon :name="step.icons[dot - 1]" class="size-3.5" />
              </span>
            </div>
            <b>{{ step.number }}</b>
            <h3>{{ step.title }}</h3>
            <p>{{ step.text }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="section audience">
      <div class="shell">
        <div class="section-heading">
          <p class="eyebrow">Для кого</p>
          <h2>Тем, кто повторяет одни и те же действия каждый день</h2>
        </div>
        <div class="audience-grid">
          <article v-for="item in audience" :key="item.title" class="audience-card">
            <span class="audience-icon"><UIcon :name="item.icon" class="size-6" /></span>
            <h3>{{ item.title }}</h3>
            <p>{{ item.text }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="section !pt-0">
      <div class="shell">
        <div class="cta-band">
          <div>
            <p class="eyebrow !mb-3 !text-[#3d4a12]">Бесплатный старт</p>
            <h2>Соберите первую цепочку сегодня</h2>
          </div>
          <UButton to="/login" size="xl" color="neutral" label="Создать аккаунт" trailing-icon="i-lucide-arrow-up-right" />
        </div>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
const unique = [
  { icon: 'i-lucide-mouse-pointer-click', title: 'Визуальный редактор', text: 'Цепочка собирается на холсте: видно каждый шаг, связь и результат.' },
  { icon: 'i-lucide-wallet', title: 'Платите за запуск', text: 'Дороже тариф — больше кредитов. Функции одинаковы на всех планах.' },
  { icon: 'i-lucide-calendar-clock', title: 'По кнопке или по расписанию', text: 'Разовые задачи и ежедневные отчёты работают в одном интерфейсе.' },
  { icon: 'i-lucide-send', title: 'Результат в Telegram', text: 'Не нужно открывать кабинет, чтобы получить готовый ответ.' }
]
const features = [
  { number: '01 / ПОИСК', title: 'Следите за важным, а не за вкладками', text: 'Новости, упоминания, цены и любые изменения в сети собираются автоматически по вашему запросу.', icon: 'i-lucide-search', accent: '#2bbf8e' },
  { number: '02 / ОБРАБОТКА', title: 'Получайте выводы, а не сырой текст', text: 'Краткое резюме, сравнение или отчёт в нужном формате — по инструкции, которую вы пишете своими словами.', icon: 'i-lucide-sparkles', accent: '#8b7cff' },
  { number: '03 / ДОСТАВКА', title: 'Результат приходит сам', text: 'Готовый текст появляется в Telegram сразу после запуска. Не нужно проверять статус или копировать ответы.', icon: 'i-lucide-send', accent: '#2aa8e0' }
]
const steps = [
  { id: 'assemble', number: '01', title: 'Соберите действия', text: 'Перетащите на холст поиск, обработку и отправку в Telegram — как блоки конструктора.', icons: ['i-lucide-search', 'i-lucide-sparkles', 'i-lucide-send'] },
  { id: 'describe', number: '02', title: 'Опишите результат', text: 'Напишите, что найти и что сделать с найденным. Не нужен код, промпт-инженерия или сервер.', icons: ['i-lucide-type', 'i-lucide-braces', 'i-lucide-check'] },
  { id: 'run', number: '03', title: 'Запустите или поставьте расписание', text: 'Ayakun покажет оценку стоимости и выполнит цепочку по кнопке или в нужное время.', icons: ['i-lucide-play', 'i-lucide-clock', 'i-lucide-bell'] }
]
const audience = [
  { icon: 'i-lucide-briefcase', title: 'Специалисты и команды', text: 'Мониторинг рынка, конкурентов и новостей без ручной сводки каждое утро.' },
  { icon: 'i-lucide-pen-line', title: 'Авторы и аналитики', text: 'Сбор источников и короткие выжимки приходят сами — остаётся решение.' },
  { icon: 'i-lucide-building-2', title: 'Малый бизнес', text: 'Регулярные отчёты и уведомления без разработчика и отдельного сервера.' }
]

</script>
