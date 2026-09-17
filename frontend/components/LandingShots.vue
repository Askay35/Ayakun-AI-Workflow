<template>
  <div class="shot-story">
    <figure class="shot-card is-dark reveal">
      <img src="/images/workflow2.png" alt="Цепочка: поиск вакансий Laravel, обработка и отправка в Telegram" width="1920" height="908" loading="lazy" />
      <figcaption>
        <span class="shot-step">01 · Цепочка</span>
        <strong>Вакансии Laravel за неделю</strong>
        <p>Поиск → ИИ собирает сообщение → Telegram.</p>
      </figcaption>
    </figure>

    <div class="shot-split">
      <figure class="shot-card is-light reveal" style="animation-delay: 80ms">
        <img src="/images/workflow_run.png" class="step-2-img" alt="Страница запуска: прогресс 100% и найденные вакансии" width="1600" height="900" loading="lazy" />
        <figcaption>
          <span class="shot-step">02 · Запуск</span>
          <strong>Результат в кабинете</strong>
          <p>Каждое звено видно, credits списаны по факту.</p>
        </figcaption>
      </figure>
      <figure class="shot-card is-phone reveal" style="animation-delay: 140ms">
        <img src="/images/tg.png" alt="Сообщение в Telegram со списком вакансий Laravel" width="720" height="1280" loading="lazy" />
        <figcaption>
          <span class="shot-step">03 · Telegram</span>
          <strong>Готовый список в чат</strong>
          <p>То, что собрала цепочка, приходит сообщением.</p>
        </figcaption>
      </figure>
    </div>

    <figure class="shot-card is-dark reveal" style="animation-delay: 180ms">
      <img src="/images/workflow.png" alt="Большая цепочка: вебхук, HTTP, ветвления в Telegram, почту, таблицы и базу" width="1920" height="908" loading="lazy" />
      <figcaption>
        <span class="shot-step">Ещё сценарий</span>
        <strong>Ветвления на одном холсте</strong>
        <p>Вебхук и HTTP расходятся в Telegram, почту, таблицы и SQL.</p>
      </figcaption>
    </figure>
  </div>
</template>
<style scoped>
.step-2-img {
  height: 100%;
  object-fit: cover;
  object-position: -290px -1px!important;
}
</style>