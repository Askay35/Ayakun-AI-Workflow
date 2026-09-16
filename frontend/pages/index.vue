<template>
  <main>
    <section class="hero">
      <div class="shell hero-grid">
        <div class="reveal">
          <p class="eyebrow">Визуальные AI-цепочки</p>
          <h1>Автоматизация,<br><span class="hero-shine">которую видно</span></h1>
          <p class="hero-copy">
            Соберите на холсте поиск, ИИ, таблицы, почту, HTTP и условия —
            как конструктор. Одна цепочка заменяет рутину: от входящего события
            до письма, строки в таблице или сообщения в Telegram.
          </p>
          <div class="hero-actions">
            <UButton to="/login" size="xl" label="Начать бесплатно" trailing-icon="i-lucide-arrow-right" />
            <UButton to="/#examples" size="xl" label="Смотреть примеры" class="text-white!" color="neutral" variant="outline" />
          </div>
          <div class="trust-row">
            <span><UIcon name="i-lucide-check-circle-2" /> Без кода и серверов</span>
            <span><UIcon name="i-lucide-check-circle-2" /> Цена видна до запуска</span>
            <span><UIcon name="i-lucide-check-circle-2" /> 200 credits при регистрации</span>
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
          <h2>Десять звеньев — любые сценарии</h2>
          <p>Поиск и Telegram — только начало. Добавьте таблицы, почту, вебхук, базу и ветвления так, как устроена ваша задача.</p>
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
  { icon: 'i-lucide-mouse-pointer-click', title: 'Холст вместо кода', text: 'Каждое звено, связь и ветка на одном экране — цепочку видно целиком, как схему.' },
  { icon: 'i-lucide-unplug', title: 'Таблицы, почта, события', text: 'Google Таблицы, Gmail, вебхуки и базы рядом с поиском и ИИ — без своего сервера.' },
  { icon: 'i-lucide-calendar-clock', title: 'По кнопке, расписанию или событию', text: 'Утренний дайджест, реакция на вебхук или разовый запуск — в одном редакторе.' },
  { icon: 'i-lucide-wallet', title: 'Платите за запуск', text: 'Стоимость видна до старта. На всех тарифах одни и те же звенья, отличается запас credits.' }
]

const blocks = [
  { number: '01', title: 'Поиск в сети', text: 'Свежие новости, вакансии, цены, упоминания бренда — всё, что можно найти по запросу.', icon: 'i-lucide-search', accent: '#2bbf8e' },
  { number: '02', title: 'Обработка', text: 'Сжать, сравнить, написать письмо или отчёт в нужном формате — своими словами.', icon: 'i-lucide-sparkles', accent: '#8b7cff' },
  { number: '03', title: 'HTTP-запрос', text: 'Подтянуть данные из CRM, курса валют, своей админки или любого API.', icon: 'i-lucide-globe', accent: '#f59e0b' },
  { number: '04', title: 'IF ELSE', text: 'Ветвление: если цена упала — одно действие, если нет — другое. Без лишнего шума.', icon: 'i-lucide-git-branch', accent: '#e8b84a' },
  { number: '05', title: 'Telegram', text: 'Готовый результат уходит в чат сразу после запуска — вам или команде.', icon: 'i-lucide-send', accent: '#2aa8e0' },
  { number: '06', title: 'Вебхук', text: 'Цепочка стартует по событию: новая заявка, оплата, форма на сайте.', icon: 'i-lucide-webhook', accent: '#f472b6' },
  { number: '07', title: 'Google Таблицы', text: 'Читать и писать строки: лиды, прайс, отчёт — без ручного копирования.', icon: 'i-lucide-table', accent: '#22c55e' },
  { number: '08', title: 'Gmail', text: 'Отправить письмо или забрать входящие через Google-аккаунт и передать дальше по цепочке.', icon: 'i-lucide-mail', accent: '#ea4335' },
  { number: '09', title: 'Преобразование', text: 'Отфильтровать, разложить и собрать JSON так, чтобы следующее звено поняло данные.', icon: 'i-lucide-replace', accent: '#38bdf8' },
  { number: '10', title: 'База данных', text: 'SQL-запрос к PostgreSQL, MySQL или ClickHouse: остатки, заказы, метрики — сразу в цепочку.', icon: 'i-lucide-database', accent: '#6366f1' }
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
    title: 'Заявка с сайта → строка и чат',
    text: 'Вебхук ловит форму, преобразование приводит поля к виду таблицы, строка пишется в Google Таблицы, команда получает апдейт в Telegram.',
    chain: ['Вебхук', 'Таблица', 'Telegram'],
    icons: ['i-lucide-webhook', 'i-lucide-table', 'i-lucide-send'],
    accents: ['#f472b6', '#22c55e', '#2aa8e0']
  },
  {
    tag: 'Продажи',
    schedule: 'По входящему письму',
    title: 'Письмо клиента → задача в таблице',
    text: 'Gmail забирает новое письмо, ИИ выделяет суть и следующий шаг, строка появляется в таблице — ничего не теряется во входящих.',
    chain: ['Gmail', 'ИИ: суть', 'Google Таблицы'],
    icons: ['i-lucide-mail', 'i-lucide-sparkles', 'i-lucide-table'],
    accents: ['#ea4335', '#8b7cff', '#22c55e']
  },
  {
    tag: 'Склад',
    schedule: 'Каждый час',
    title: 'Остатки из базы, если кончается товар',
    text: 'SQL читает остатки, условие отсекает норму, и только по дефициту уходит письмо закупщику — без ложных тревог.',
    chain: ['SQL', 'IF: мало', 'Gmail'],
    icons: ['i-lucide-database', 'i-lucide-git-branch', 'i-lucide-mail'],
    accents: ['#6366f1', '#e8b84a', '#ea4335']
  }
]

const steps = [
  {
    id: 'assemble',
    number: '01',
    title: 'Соберите блоки на холсте',
    text: 'Перетащите поиск, ИИ, Gmail, таблицы, SQL, HTTP или Telegram и соедините выходы со входами — как в визуальном конструкторе.',
    icons: ['i-lucide-search', 'i-lucide-sparkles', 'i-lucide-mail', 'i-lucide-database', 'i-lucide-send']
  },
  {
    id: 'describe',
    number: '02',
    title: 'Задайте правила обычным языком',
    text: 'Что искать, какой промпт, какой запрос к базе, при каком условии идти дальше и куда отправить результат. Без кода и без отдельного сервера.',
    icons: ['i-lucide-type', 'i-lucide-braces', 'i-lucide-git-branch']
  },
  {
    id: 'run',
    number: '03',
    title: 'Запустите или поставьте расписание',
    text: 'Оценка стоимости видна заранее. Запуск — по кнопке, по вебхуку или в нужное время; результат приходит в кабинет, в Gmail или в Telegram.',
    icons: ['i-lucide-play', 'i-lucide-clock', 'i-lucide-mail']
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
    example: 'Пример: SQL заказы → ИИ-сводка → Gmail'
  },
  {
    icon: 'i-lucide-code-2',
    title: 'Разработчики и no-code',
    text: 'Быстрые интеграции и ветвления без поднятия своего n8n или воркеров.',
    example: 'Пример: вебхук → условие → таблица или Telegram'
  }
]
</script>
