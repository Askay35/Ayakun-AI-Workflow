# Как устроен граф workflow

Граф — это список узлов. Отдельного массива рёбер нет: связь кодируется на самих узлах.

## Поле `draft_graph` / `graph_snapshot`

```json
{
  "nodes": [
    {
      "id": "search-1",
      "type": "web_search",
      "parents": [],
      "children": ["prompt-1"],
      "position": { "x": 80, "y": 160 },
      "label": "Поиск в сети",
      "query": "новости рынка",
      "period": null
    },
    {
      "id": "prompt-1",
      "type": "prompt",
      "parents": ["search-1"],
      "children": ["tg-1"],
      "position": { "x": 420, "y": 160 },
      "label": "Обработка",
      "prompt": "сделай краткое саммари",
      "instructions": "",
      "complexity": "simple_text"
    },
    {
      "id": "tg-1",
      "type": "telegram_send",
      "parents": ["prompt-1"],
      "children": [],
      "position": { "x": 760, "y": 160 },
      "label": "Telegram",
      "chat_id": null
    }
  ]
}
```

Связь всегда двусторонняя: если A указывает B в `children`, у B в `parents` есть A. Бэкенд восстанавливает это при разборе графа.

## Типы узлов

| `type` | Входы | Выходы | Поля узла |
|---|---|---|---|
| `web_search` | 0+ | 0+ | `query`, `period` |
| `prompt` | 0+ | 0+ | `prompt`, `instructions`, `provider`, `model`, `complexity` |
| `telegram_send` | ровно 1 при публикации | всегда 0 | `chat_id` (можно пустой — берётся Telegram владельца) |

Общие поля: `id`, `type`, `parents`, `children`, `position`, `label`.

Редактор рисует стрелки из `children`. На сервер уходит только массив `nodes`.

## Таблицы

```
users
  └── workflows                  черновик живёт здесь
        ├── draft_graph JSONB    текущий граф из редактора
        ├── published_version_id → workflow_versions.id
        └── workflow_versions
              └── graph_snapshot JSONB   неизменяемая копия на момент publish
                    └── workflow_runs    один запуск снимка
                          ├── input / output JSONB   вход всего run и выходы узлов
                          └── node_runs              шаг каждого узла
```

| Таблица | Роль |
|---|---|
| `workflows` | Цепочка пользователя. `draft_graph` — то, что редактируется. |
| `workflow_versions` | Снимок графа после «Опубликовать». Run всегда идёт по снимку, не по черновику. |
| `workflow_runs` | Запуск: статус, `input` (параметры run), `output` (карта `{node_id: {type, output}}`). |
| `node_runs` | Исполнение одного узла: его конфиг в `input`, результат в `output`. |

## Как данные идут по цепочке

1. Клиент `PATCH /workflows/{id}` с `{ graph: { nodes } }`.
2. Worker обходит узлы в порядке родителей → детей.
3. Для узла берётся `node.parents`, из `context["nodes"]` читается output родителей и передаётся в executor (`prompt` / `telegram_send`).

Telegram получает текст единственного родителя и никому дальше его не отдаёт.
