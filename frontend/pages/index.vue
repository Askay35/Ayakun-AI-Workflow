<template>
  <main>
    <section class="hero">
      <div class="shell hero-grid">
        <div class="reveal">
          <p class="eyebrow">Автоматизация без разработки</p>
          <h1>Рутина работает. <span>Вы — решаете.</span></h1>
          <p class="hero-copy">
            Соберите цепочку из поиска, анализа и отправки результата.
            Ayakun выполнит её по кнопке или расписанию — без кода, серверов и ручного контроля.
          </p>
          <div class="hero-actions">
            <UButton to="/login" size="xl" label="Собрать первую цепочку" trailing-icon="i-lucide-arrow-right" />
            <UButton to="/#how" size="xl" label="Посмотреть, как работает" class="text-white!" color="neutral" variant="outline" />
          </div>
          <div class="trust-row">
            <span><UIcon name="i-lucide-check-circle-2" /> Бесплатный старт</span>
            <span><UIcon name="i-lucide-check-circle-2" /> Расписание на любом тарифе</span>
            <span><UIcon name="i-lucide-check-circle-2" /> Цена известна до запуска</span>
          </div>
        </div>

        <div class="workflow-demo reveal" style="animation-delay: 140ms">
          <div class="demo-toolbar">
            <div>
              <p class="m-0 text-sm font-extrabold">Мониторинг конкурентов</p>
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

    <section class="section alt">
      <div class="shell">
        <div class="section-heading">
          <p class="eyebrow">Что можно автоматизировать</p>
          <h2>От запроса до готового результата — в одной цепочке</h2>
          <p>Настройте один раз. Дальше Ayakun сам найдёт данные, обработает их по вашим правилам и доставит туда, где вы уже работаете.</p>
        </div>
        <div class="feature-grid">
          <article class="feature-card">
            <span class="feature-number">01 / ПОИСК</span>
            <h3>Следите за важным, а не за вкладками</h3>
            <p>Новости рынка, упоминания бренда, цены конкурентов и любые изменения в сети — автоматически.</p>
          </article>
          <article class="feature-card">
            <span class="feature-number">02 / ОБРАБОТКА</span>
            <h3>Получайте выводы, а не сырой текст</h3>
            <p>Краткое резюме, сравнение, классификация или отчёт в нужном формате — по вашему заданию.</p>
          </article>
          <article class="feature-card">
            <span class="feature-number">03 / ДОСТАВКА</span>
            <h3>Результат приходит сам</h3>
            <p>Отчёт появится в Telegram сразу после выполнения. Никаких проверок статуса и ручных копирований.</p>
          </article>
        </div>
      </div>
    </section>

    <section id="how" class="section">
      <div class="shell">
        <div class="section-heading">
          <p class="eyebrow">Три простых шага</p>
          <h2>Первая автоматизация — за несколько минут</h2>
        </div>
        <div class="steps">
          <article class="step"><b>01</b><h3>Добавьте действия</h3><p>Перетащите на поле поиск, обработку и отправку сообщения.</p></article>
          <article class="step"><b>02</b><h3>Опишите результат</h3><p>Напишите обычными словами, что найти и что сделать с найденным.</p></article>
          <article class="step"><b>03</b><h3>Запустите или назначьте время</h3><p>Ayakun покажет цену заранее и выполнит цепочку по кнопке или расписанию.</p></article>
        </div>
      </div>
    </section>

    <section class="section !pt-0">
      <div class="shell">
        <div class="cta-band">
          <h2>Освободите время от повторяющихся задач</h2>
          <UButton to="/login" size="xl" color="neutral" label="Начать бесплатно" trailing-icon="i-lucide-arrow-up-right" />
        </div>
      </div>
    </section>
  </main>
</template>
