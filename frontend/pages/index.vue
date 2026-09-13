<template>
  <main>
    <section class="hero">
      <div class="shell hero-grid">
        <div class="reveal">
          <p class="eyebrow">Визуальные AI-цепочки</p>
          <h1>Автоматизация,<br>которую видно</h1>
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
            <span><UIcon name="i-lucide-check-circle-2" /> Цена видна до запуска</span>
            <span><UIcon name="i-lucide-check-circle-2" /> 1000 credits при регистрации</span>
          </div>
        </div>

        <div class="workflow-demo reveal" style="animation-delay: 140ms">
          <div class="demo-toolbar">
            <div>
              <p class="m-0 text-sm font-extrabold">Утренний обзор рынка</p>
              <p class="m-0 mt-1 text-xs muted">Каждый будний день, 09:00</p>
            </div>
            <div class="demo-dots"><i /><i /><i /></div>
          </div>
          <div class="demo-node">
            <div class="demo-node-head"><span class="demo-icon"><UIcon name="i-lucide-search" /></span>Найти свежие новости</div>
            <div class="demo-text" /><div class="demo-text short" />
          </div>
          <div class="demo-node">
            <div class="demo-node-head"><span class="demo-icon"><UIcon name="i-lucide-sparkles" /></span>Выделить главное</div>
            <div class="demo-text" /><div class="demo-text short" />
          </div>
          <div class="demo-node">
            <div class="demo-node-head"><span class="demo-icon"><UIcon name="i-lucide-send" /></span>Прислать в Telegram</div>
            <div class="demo-text short" />
          </div>
          <div class="demo-price"><UIcon name="i-lucide-coins" class="mr-1" />≈ 2 credits / запуск</div>
        </div>
      </div>
    </section>

    <section class="unique-strip">
      <div class="shell unique-grid">
        <article v-for="item in unique" :key="item.title" class="unique-card">
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
          <article class="feature-card">
            <span class="feature-number">01 / ПОИСК</span>
            <h3>Следите за важным, а не за вкладками</h3>
            <p>Новости, упоминания, цены и любые изменения в сети собираются автоматически по вашему запросу.</p>
          </article>
          <article class="feature-card">
            <span class="feature-number">02 / ОБРАБОТКА</span>
            <h3>Получайте выводы, а не сырой текст</h3>
            <p>Краткое резюме, сравнение или отчёт в нужном формате — по инструкции, которую вы пишете своими словами.</p>
          </article>
          <article class="feature-card">
            <span class="feature-number">03 / ДОСТАВКА</span>
            <h3>Результат приходит сам</h3>
            <p>Готовый текст появляется в Telegram сразу после запуска. Не нужно проверять статус или копировать ответы.</p>
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
        <div class="steps">
          <article class="step">
            <b>01</b>
            <h3>Соберите действия</h3>
            <p>Перетащите на холст поиск, обработку и отправку в Telegram — как блоки конструктора.</p>
          </article>
          <article class="step">
            <b>02</b>
            <h3>Опишите результат</h3>
            <p>Напишите, что найти и что сделать с найденным. Не нужен код, промпт-инженерия или сервер.</p>
          </article>
          <article class="step">
            <b>03</b>
            <h3>Запустите или поставьте расписание</h3>
            <p>Ayakun покажет оценку стоимости и выполнит цепочку по кнопке или в нужное время.</p>
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
const audience = [
  { icon: 'i-lucide-briefcase', title: 'Специалисты и команды', text: 'Мониторинг рынка, конкурентов и новостей без ручной сводки каждое утро.' },
  { icon: 'i-lucide-pen-line', title: 'Авторы и аналитики', text: 'Сбор источников и короткие выжимки приходят сами — остаётся решение.' },
  { icon: 'i-lucide-building-2', title: 'Малый бизнес', text: 'Регулярные отчёты и уведомления без разработчика и отдельного сервера.' }
]
</script>
