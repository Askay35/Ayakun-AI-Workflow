<template>
  <main>
    <section class="hero">
      <div class="shell hero-grid">
        <div class="reveal">
          <p class="eyebrow">Визуальные AI-цепочки</p>
          <h1>Автоматизация,<br><span class="hero-shine">которую видно</span></h1>
          <p class="hero-copy">
            Соберите на холсте поиск, ИИ, HTTP-запросы, условия и Telegram —
            как конструктор. Одна цепочка заменяет рутину: от сбора данных
            до решения «что делать дальше» и готового сообщения.
          </p>
          <div class="hero-actions">
            <UButton to="/login" size="xl" label="Начать бесплатно" trailing-icon="i-lucide-arrow-right" />
            <UButton to="/#examples" size="xl" label="Смотреть примеры" class="text-white!" color="neutral" variant="outline" />
          </div>
          <div class="trust-row">
            <span><UIcon name="i-lucide-check-circle-2" /> Без кода и серверов</span>
            <span><UIcon name="i-lucide-check-circle-2" /> Цена видна до запуска</span>
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
          <p class="eyebrow">Блоки цепочки</p>
          <h2>Пять действий — любые сценарии</h2>
          <p>Не только «поиск → промпт → Telegram». Соединяйте источники, ИИ, API и ветвления так, как устроена ваша задача.</p>
        </div>
        <div class="blocks-grid">
          <article v-for="card in blocks" :key="card.title" class="feature-card">
            <span class="feature-number">{{ card.number }}</span>
            <span class="feature-icon" :style="{ color: card.accent, background: `${card.accent}22` }">
              <UIcon :name="card.icon" class="size-5" />
            </span>
            <h3>{{ card.title }}</h3>
            <p>{{ card.text }}</p>
          </article>
        </div>
      </div>
    </section>

    <section id="examples" class="section">
      <div class="shell">
        <div class="section-heading">
          <p class="eyebrow">Примеры цепочек</p>
          <h2>Соберите сценарий под свою рутину</h2>
          <p>Ниже — готовые идеи. В редакторе вы меняете запросы, условия и текст сообщений под себя.</p>
        </div>
        <div class="examples-grid">
          <article v-for="example in examples" :key="example.title" class="example-card">
            <div class="example-top">
              <span class="example-tag">{{ example.tag }}</span>
              <span class="example-schedule">{{ example.schedule }}</span>
            </div>
            <h3>{{ example.title }}</h3>
            <p>{{ example.text }}</p>
            <div class="example-chain">
              <template v-for="(step, index) in example.chain" :key="`${example.title}-${step}`">
                <span class="example-step" :style="{ '--step-accent': example.accents[index] }">
                  <UIcon :name="example.icons[index]" class="size-3.5" />
                  {{ step }}
                </span>
                <UIcon v-if="index < example.chain.length - 1" name="i-lucide-arrow-right" class="example-arrow" />
              </template>
            </div>
          </article>
        </div>
      </div>
    </section>

    <section id="how" class="section how-section">
      <div class="shell">
        <div class="section-heading">
          <p class="eyebrow">Как собрать</p>
          <h2>От идеи до работающей цепочки</h2>
        </div>
        <div class="build-track">
          <article v-for="(step, index) in steps" :key="step.title" class="build-step">
            <div class="build-visual" :class="`is-${step.id}`">
              <span v-for="dot in step.icons.length" :key="dot" class="build-chip" :style="{ animationDelay: `${index * 180 + dot * 90}ms` }">
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
          <h2>Если задача повторяется — её можно отдать цепочке</h2>
        </div>
        <div class="audience-grid audience-grid-wide">
          <article v-for="item in audience" :key="item.title" class="audience-card">
            <span class="audience-icon"><UIcon :name="item.icon" class="size-6" /></span>
            <h3>{{ item.title }}</h3>
            <p>{{ item.text }}</p>
            <p class="audience-example">{{ item.example }}</p>
          </article>
        </div>
      </div>
    </section>

    <section class="section pt-0!">
      <div class="shell">
        <div class="cta-band">
          <div>
            <p class="eyebrow !mb-3 text-[#3d4a12]!">Бесплатный старт</p>
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
  { icon: 'i-lucide-mouse-pointer-click', title: 'Визуальный редактор', text: 'Цепочка на холсте: каждый блок, связь и ветка видны сразу.' },
  { icon: 'i-lucide-git-branch', title: 'Условия и API', text: 'IF ELSE и HTTP-запросы — не только поиск и Telegram.' },
  { icon: 'i-lucide-calendar-clock', title: 'По кнопке или по расписанию', text: 'Разовые задачи и ежедневные сценарии в одном интерфейсе.' },
  { icon: 'i-lucide-wallet', title: 'Платите за запуск', text: 'Дороже тариф — больше кредитов. Функции одинаковы на всех планах.' }
]

const blocks = [
  { number: '01', title: 'Поиск в сети', text: 'Свежие новости, вакансии, цены, упоминания бренда — всё, что можно найти по запросу.', icon: 'i-lucide-search', accent: '#2bbf8e' },
  { number: '02', title: 'ИИ-промпт', text: 'Сжать, сравнить, написать письмо или отчёт в нужном формате — своими словами.', icon: 'i-lucide-sparkles', accent: '#8b7cff' },
  { number: '03', title: 'HTTP-запрос', text: 'Подтянуть данные из CRM, курса валют, своей админки или любого API.', icon: 'i-lucide-globe', accent: '#f59e0b' },
  { number: '04', title: 'IF ELSE', text: 'Ветвление: если цена упала — одно действие, если нет — другое. Без лишнего шума.', icon: 'i-lucide-git-branch', accent: '#e8b84a' },
  { number: '05', title: 'Telegram', text: 'Готовый результат уходит в чат сразу после запуска — вам или команде.', icon: 'i-lucide-send', accent: '#2aa8e0' }
]

const examples = [
  {
    tag: 'Карьера',
    schedule: 'Каждый день · 10:00',
    title: 'Новые вакансии без ручного серфинга',
    text: 'Утром сервис ищет свежие позиции, ИИ отбирает подходящие и формулирует короткое сообщение — вам остаётся открыть Telegram.',
    chain: ['Поиск вакансий', 'ИИ: отбор и текст', 'Telegram'],
    icons: ['i-lucide-search', 'i-lucide-sparkles', 'i-lucide-send'],
    accents: ['#2bbf8e', '#8b7cff', '#2aa8e0']
  },
  {
    tag: 'Мониторинг',
    schedule: 'По кнопке или по крону',
    title: 'Цена конкурента с умным порогом',
    text: 'HTTP забирает цену из API, условие проверяет порог, и только при снижении ИИ пишет алерт в Telegram.',
    chain: ['HTTP API', 'IF: цена ниже', 'ИИ → Telegram'],
    icons: ['i-lucide-globe', 'i-lucide-git-branch', 'i-lucide-send'],
    accents: ['#f59e0b', '#e8b84a', '#2aa8e0']
  },
  {
    tag: 'Контент',
    schedule: 'Пн–Пт · 08:30',
    title: 'Утренний дайджест ниши',
    text: 'Поиск собирает новости, промпт делает выжимку в вашем тоне, Telegram присылает готовую сводку до кофе.',
    chain: ['Поиск новостей', 'ИИ: дайджест', 'Telegram'],
    icons: ['i-lucide-search', 'i-lucide-sparkles', 'i-lucide-send'],
    accents: ['#2bbf8e', '#8b7cff', '#2aa8e0']
  },
  {
    tag: 'Операции',
    schedule: 'После события',
    title: 'Статус из CRM → понятное сообщение',
    text: 'HTTP читает заказ или лид, ИИ переводит сырой JSON в человеческий текст, команда получает апдейт в чат.',
    chain: ['HTTP CRM', 'ИИ: формулировка', 'Telegram'],
    icons: ['i-lucide-globe', 'i-lucide-sparkles', 'i-lucide-send'],
    accents: ['#f59e0b', '#8b7cff', '#2aa8e0']
  }
]

const steps = [
  {
    id: 'assemble',
    number: '01',
    title: 'Соберите блоки на холсте',
    text: 'Перетащите поиск, ИИ, HTTP, условие или Telegram и соедините выходы со входами — как в визуальном конструкторе.',
    icons: ['i-lucide-search', 'i-lucide-sparkles', 'i-lucide-globe', 'i-lucide-git-branch', 'i-lucide-send']
  },
  {
    id: 'describe',
    number: '02',
    title: 'Задайте правила обычным языком',
    text: 'Что искать, какой промпт, какой URL, при каком условии идти дальше. Без кода и без отдельного сервера.',
    icons: ['i-lucide-type', 'i-lucide-braces', 'i-lucide-sliders-horizontal']
  },
  {
    id: 'run',
    number: '03',
    title: 'Запустите или поставьте расписание',
    text: 'Оценка стоимости видна заранее. Запуск — по кнопке или в нужное время; результат приходит в кабинет и в Telegram.',
    icons: ['i-lucide-play', 'i-lucide-clock', 'i-lucide-bell']
  }
]

const audience = [
  {
    icon: 'i-lucide-briefcase',
    title: 'Специалисты и менеджеры',
    text: 'Ежедневный мониторинг рынка, конкурентов и новостей без ручной сводки.',
    example: 'Пример: поиск упоминаний → ИИ-резюме → Telegram'
  },
  {
    icon: 'i-lucide-user-round-search',
    title: 'Соискатели',
    text: 'Не пролистывать десятки сайтов — получать отобранные вакансии одним сообщением.',
    example: 'Пример: поиск вакансий → ИИ-отбор → Telegram'
  },
  {
    icon: 'i-lucide-pen-line',
    title: 'Авторы и аналитики',
    text: 'Сбор источников и короткие выжимки приходят сами — остаётся мысль и публикация.',
    example: 'Пример: поиск статей → ИИ-конспект → Telegram'
  },
  {
    icon: 'i-lucide-trending-up',
    title: 'Маркетологи и growth',
    text: 'Следить за ценами, офферами и активностью конкурентов по расписанию.',
    example: 'Пример: HTTP прайс → IF порог → алерт в Telegram'
  },
  {
    icon: 'i-lucide-building-2',
    title: 'Малый бизнес',
    text: 'Регулярные отчёты и уведомления без разработчика и отдельной инфраструктуры.',
    example: 'Пример: HTTP заказы → ИИ-сводка → Telegram'
  },
  {
    icon: 'i-lucide-code-2',
    title: 'Разработчики и no-code',
    text: 'Быстрые интеграции и ветвления без поднятия своего n8n или воркеров.',
    example: 'Пример: webhook/API → условие → ИИ или Telegram'
  }
]
</script>
