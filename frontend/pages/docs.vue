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
  loopTaken: '{% for item in $data %}',
  loopFree: '{% for row in $data %}',
  transformInput: '{\n  "data": [\n    { "id": 1, "name": "BTC", "symbol": "BTC", "score": 3, "secret": "x" },\n    { "id": 2, "name": "ETH", "symbol": "ETH", "score": 1, "secret": "y" }\n  ]\n}',
  transformPath: 'data',
  selectFields: 'id, name, score',
  selectOut: '[\n  { "id": 1, "name": "BTC", "score": 3 },\n  { "id": 2, "name": "ETH", "score": 1 }\n]',
  renameMap: 'name=title\nscore=points',
  renameOut: '[\n  { "id": 1, "title": "BTC", "symbol": "BTC", "points": 3, "secret": "x" },\n  { "id": 2, "title": "ETH", "symbol": "ETH", "points": 1, "secret": "y" }\n]',
  setMap: 'status=active\nlabel={{$name}}',
  setOut: '[\n  { "id": 1, "name": "BTC", "symbol": "BTC", "score": 3, "secret": "x", "status": "active", "label": "BTC" },\n  { "id": 2, "name": "ETH", "symbol": "ETH", "score": 1, "secret": "y", "status": "active", "label": "ETH" }\n]',
  removeFields: 'secret, symbol',
  removeOut: '[\n  { "id": 1, "name": "BTC", "score": 3 },\n  { "id": 2, "name": "ETH", "score": 1 }\n]',
  filterCondition: '{{$score}} >= 2',
  filterOut: '[\n  { "id": 1, "name": "BTC", "symbol": "BTC", "score": 3, "secret": "x" }\n]',
  sortField: 'score',
  sortOut: '[\n  { "id": 2, "name": "ETH", "symbol": "ETH", "score": 1, "secret": "y" },\n  { "id": 1, "name": "BTC", "symbol": "BTC", "score": 3, "secret": "x" }\n]',
  map: '{\n  "title": "{{$name}}",\n  "symbol": "{{$symbol}}",\n  "points": "{{$score}}"\n}',
  mapOut: '[\n  { "title": "BTC", "symbol": "BTC", "points": 3 },\n  { "title": "ETH", "symbol": "ETH", "points": 1 }\n]',
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
          <li><strong>Ctrl</strong> (на Mac — ⌘) или <strong>Shift</strong> + клик добавляет узел к выбору или снимает его. <strong>Shift</strong> + рамка выделяет все узлы, которых коснулась.</li>
          <li><strong>Delete</strong> или <strong>Backspace</strong> удаляет все выбранные узлы вместе со связями. Наведите на стрелку — в середине появится крестик, чтобы убрать только связь.</li>
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
        <p>
          Циклы можно вкладывать. Тело цикла — обычный текст с теми же подстановками.
          Имя элемента цикла не должно совпадать с уже заданной переменной цепочки:
          если есть переменная <code>item</code>, пишите <code>{{ examples.loopFree }}</code>, а не
          <code>{{ examples.loopTaken }}</code> — иначе запуск остановится с ошибкой.
        </p>

        <h2>Telegram</h2>
        <ul>
          <li>Если текст сообщения пустой, уходит весь JSON или текст предыдущего узла — не только заголовки.</li>
          <li>Чтобы отправить JSON явно, напишите <code>{{ examples.root }}</code>.</li>
          <li>Чтобы красиво перечислить массив, используйте цикл, как в примере выше.</li>
        </ul>

        <h2>Преобразование данных</h2>
        <p>
          Узел берёт JSON предыдущего шага и меняет его. Поле «Путь к данным» указывает, какой кусок входа брать:
          пусто — весь вход, <code>{{ examples.transformPath }}</code> — массив внутри объекта.
          Если по пути массив, операция применяется к каждому элементу (Sort всегда ждёт массив).
        </p>
        <p>Пример входа для операций ниже (путь <code>{{ examples.transformPath }}</code>):</p>
        <pre><code>{{ examples.transformInput }}</code></pre>

        <h3>Select — оставить поля</h3>
        <p>Оставляет только перечисленные ключи. Остальные отбрасываются. Поля пишутся через запятую или JSON-массивом.</p>
        <p>Поля: <code>{{ examples.selectFields }}</code></p>
        <pre><code>{{ examples.selectOut }}</code></pre>

        <h3>Rename — переименовать</h3>
        <p>Меняет имена ключей, значения не трогает. Строки вида <code>старое=новое</code> или JSON-объект.</p>
        <pre><code>{{ examples.renameMap }}</code></pre>
        <pre><code>{{ examples.renameOut }}</code></pre>

        <h3>Set — задать значения</h3>
        <p>Добавляет или перезаписывает поля. Справа можно писать константу или подстановку из текущего элемента.</p>
        <pre><code>{{ examples.setMap }}</code></pre>
        <pre><code>{{ examples.setOut }}</code></pre>

        <h3>Remove — удалить поля</h3>
        <p>Убирает перечисленные ключи, остальное сохраняет.</p>
        <p>Поля: <code>{{ examples.removeFields }}</code></p>
        <pre><code>{{ examples.removeOut }}</code></pre>

        <h3>Filter — отфильтровать</h3>
        <p>Оставляет элементы, для которых условие истинно. Синтаксис тот же, что у IF ELSE; пути читаются от элемента, не от всего входа.</p>
        <p>Условие: <code>{{ examples.filterCondition }}</code></p>
        <pre><code>{{ examples.filterOut }}</code></pre>

        <h3>Sort — сортировка</h3>
        <p>Сортирует массив по полю. Нужен именно массив: одиночный объект сюда не подходит. Направление — по возрастанию или убыванию.</p>
        <p>Поле: <code>{{ examples.sortField }}</code>, направление: по возрастанию.</p>
        <pre><code>{{ examples.sortOut }}</code></pre>

        <h3>Map — преобразовать элементы</h3>
        <p>Строит новый объект по шаблону для каждого элемента. В отличие от Select, можно задать другие имена полей и брать вложенные пути.</p>
        <pre><code>{{ examples.map }}</code></pre>
        <pre><code>{{ examples.mapOut }}</code></pre>
        <p>Дальше массив можно отдать в Telegram целиком или перечислить циклом.</p>

        <h2>Условие IF</h2>
        <p>Сравнивайте поля предыдущего узла: <code>{{ examples.ifScore }}</code>, <code>{{ examples.ifStatus }}</code>. Пустой / null / отсутствующее поле в одиночной проверке считается ложью.</p>
      </div>
    </div>
  </main>
</template>
