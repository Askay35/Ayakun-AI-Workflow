<script setup lang="ts">
useSeoMeta({
  title: 'Документация',
  description: 'Как собирать цепочки Ayakun: переменные, JSON, циклы и работа в редакторе'
})

const examples = {
  root: '{{$}}',
  field: '{{$name}}',
  jsonField: '{{$jsonfield}}',
  path: '{{$data[0].field}}',
  dotted: '{{$data.0.field}}',
  variable: '{{field}}',
  total: '{{total}}',
  nestedVar: '{{rows[0].title}}',
  itemPrice: '{{item.field}}',
  loopJson: '{% for item in $data %}\nНазвание: {{item.label}} цена: {{item.price}}\n{% endfor %}',
  loopVar: '{% for row in rows %}{{row.title}}{% endfor %}',
  map: '{\n  "title": "{{$name}}",\n  "symbol": "{{$symbol}}",\n  "price": "{{$data.price}}"\n}',
  ifScore: '{{$score}} >= 0.8',
  ifStatus: '{{$status}} == "active"'
}
</script>

<template>
  <main class="shell legal-page">
    <div class="legal-card reveal">
      <p class="eyebrow">Справка</p>
      <h1 class="page-title">Документация</h1>
      <p class="legal-meta muted">Базовые приёмы редактора, подстановки и циклы.</p>

      <div class="legal-body">
        <h2>Редактор</h2>
        <ul>
          <li>Перетащите узел из палитры на холст или кликните по нему — блок появится в центре.</li>
          <li>Соединяйте выход одного узла со входом следующего. У большинства узлов только одна входящая связь.</li>
          <li>Клик по узлу открывает его настройки справа.</li>
          <li><strong>Ctrl</strong> (на Mac — ⌘) + клик добавляет узел к выбору или снимает его. <strong>Shift</strong> — выделить несколько.</li>
          <li><strong>Delete</strong> или <strong>Backspace</strong> удаляет все выбранные узлы вместе со связями. Если выделена только стрелка — удаляется связь.</li>
          <li>Черновик сохраняется сам. «Опубликовать» фиксирует версию, по которой идут запуски и расписание.</li>
        </ul>

        <h2>Данные между узлами</h2>
        <p>
          Каждый узел передаёт дальше свой результат: объект, массив или текст.
          Следующий узел читает этот JSON как корень для подстановок с <code>$</code>.
        </p>
        <ul>
          <li><code>{{ examples.root }}</code> — все входные данные целиком (объект или массив станет JSON-текстом, если вставить в строку).</li>
          <li><code>{{ examples.field }}</code> или <code>{{ examples.jsonField }}</code> — поле объекта.</li>
          <li><code>{{ examples.path }}</code> — элемент массива и вложенное поле. Можно писать <code>{{ examples.dotted }}</code>.</li>
        </ul>
        <p>Если поля нет, запуск останавливается с понятной ошибкой — так проще заметить опечатку в пути.</p>

        <h2>Переменные цепочки</h2>
        <p>
          Слева в редакторе задаются переменные. В любом текстовом поле, где есть подстановки,
          пишите <code>{{ examples.variable }}</code> — без знака <code>$</code>.
        </p>
        <p>
          Узлы вроде «Обработка», HTTP, Gmail, SQL и преобразования могут записывать значения в переменные
          (блок «Переменные» в настройках узла). Дальше их читают так же: <code>{{ examples.total }}</code>.
        </p>
        <p>Вложенные поля переменной: <code>{{ examples.nestedVar }}</code> или <code>{{ examples.itemPrice }}</code> внутри цикла.</p>

        <h2>Циклы</h2>
        <p>Там, где работают поля JSON и переменные, можно пройтись по массиву:</p>
        <pre><code>{{ examples.loopJson }}</code></pre>
        <p>Источник может быть путём JSON (<code>$data</code>, <code>$jsonfield</code>) или переменной цепочки:</p>
        <pre><code>{{ examples.loopVar }}</code></pre>
        <p>Циклы можно вкладывать. Тело цикла — обычный текст с теми же подстановками.</p>

        <h2>Telegram</h2>
        <ul>
          <li>Если текст сообщения пустой, уходит весь JSON или текст предыдущего узла — не только заголовки.</li>
          <li>Чтобы отправить JSON явно, напишите <code>{{ examples.root }}</code>.</li>
          <li>Чтобы красиво перечислить массив, используйте цикл, как в примере выше.</li>
        </ul>

        <h2>Преобразование данных</h2>
        <p>
          Операция Map строит новый объект или массив по шаблону. Путь (например <code>data</code>) указывает,
          какой кусок входа брать. Шаблон элемента:
        </p>
        <pre><code>{{ examples.map }}</code></pre>
        <p>На выходе — массив таких объектов. Дальше его можно отдать в Telegram целиком или через цикл.</p>

        <h2>Условие IF</h2>
        <p>Сравнивайте поля предыдущего узла: <code>{{ examples.ifScore }}</code>, <code>{{ examples.ifStatus }}</code>. Пустой / null / отсутствующее поле в одиночной проверке считается ложью.</p>
      </div>
    </div>
  </main>
</template>
