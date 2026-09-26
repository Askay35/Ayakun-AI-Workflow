"""Готовые шаблоны цепочек. Ключей и токенов в шаблонах нет — только структура, условия и переменные."""

from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User
from models.workflow import Workflow
from schemas.common import SearchPeriod
from schemas.workflow import ScheduleSlot, WorkflowCreate, WorkflowGraph

COLUMN_WIDTH = 320
ROW_HEIGHT = 190

Link = tuple[str, str] | tuple[str, str, str]


def node(node_id: str, node_type: str, label: str, **fields: object) -> dict:
    return {"id": node_id, "type": node_type, "label": label, **fields}


def prompt(node_id: str, label: str, text: str, **fields: object) -> dict:
    return node(node_id, "prompt", label, prompt=text, complexity="simple_text", max_output_tokens=2000, **fields)


def assign(**pairs: str) -> list[dict]:
    return [{"key": key, "value": value} for key, value in pairs.items()]


@dataclass(frozen=True)
class Template:
    slug: str
    category: str
    name: str
    description: str
    name_en: str
    description_en: str
    nodes: list[dict]
    links: list[Link]
    variables: dict[str, str] = field(default_factory=dict)

    def graph(self) -> dict:
        nodes = {item["id"]: {**item, "parents": [], "children": []} for item in self.nodes}
        for link in self.links:
            source, target = link[0], link[1]
            nodes[source]["children"].append(target)
            nodes[target]["parents"].append(source)
            if len(link) == 3:
                nodes[source].setdefault(f"{link[2]}_children", []).append(target)
        depth: dict[str, int] = {}
        for node_id in [item["id"] for item in self.nodes]:
            self._depth(node_id, nodes, depth)
        columns: dict[int, list[str]] = {}
        for item in self.nodes:
            columns.setdefault(depth[item["id"]], []).append(item["id"])
        for column, ids in columns.items():
            for row, node_id in enumerate(ids):
                offset = (row - (len(ids) - 1) / 2) * ROW_HEIGHT
                nodes[node_id]["position"] = {"x": column * COLUMN_WIDTH, "y": 200 + offset}
        return {"nodes": list(nodes.values()), "variables": dict(self.variables)}

    @staticmethod
    def _depth(node_id: str, nodes: dict, cache: dict[str, int]) -> int:
        if node_id not in cache:
            parents = nodes[node_id]["parents"]
            cache[node_id] = 0 if not parents else 1 + max(Template._depth(p, nodes, cache) for p in parents)
        return cache[node_id]

    def linear(self) -> bool:
        """Список шагов без ветвлений и циклов — такой шаблон можно открыть в мобильном редакторе."""
        if any(item["type"] in {"if_else", "loop"} for item in self.nodes):
            return False
        sources = [link[0] for link in self.links]
        targets = [link[1] for link in self.links]
        return len(sources) == len(set(sources)) and len(targets) == len(set(targets))

    def node_types(self) -> list[str]:
        seen: list[str] = []
        for item in self.nodes:
            if item["type"] not in seen:
                seen.append(item["type"])
        return seen


TEMPLATES: list[Template] = [
    # ── Контент и соцсети ──────────────────────────────────────────────
    Template(
        slug="news-digest-telegram",
        category="content",
        name="Утренний дайджест новостей",
        description="Каждое утро ищет свежие новости по теме, ИИ делает короткую выжимку, итог приходит в Telegram.",
        name_en="Morning news digest",
        description_en="Every morning finds fresh news on a topic, AI makes a short summary and sends it to Telegram.",
        variables={"topic": "искусственный интеллект в бизнесе"},
        nodes=[
            node("search", "web_search", "Свежие новости", query="{{topic}} новости", period="d"),
            prompt("digest", "Короткая выжимка", "Сделай дайджест из 5 главных новостей по теме «{{topic}}». Для каждой — одна фраза сути и ссылка.",
                   instructions="Пиши по-русски, без воды, списком."),
            node("send", "telegram_send", "В Telegram", message=""),
        ],
        links=[("search", "digest"), ("digest", "send")],
    ),
    Template(
        slug="linkedin-post-from-news",
        category="content",
        name="Пост в LinkedIn по новостям ниши",
        description="Находит главное событие недели в вашей нише и публикует экспертный пост в LinkedIn.",
        name_en="LinkedIn post from industry news",
        description_en="Finds the key event of the week in your niche and publishes an expert LinkedIn post.",
        variables={"niche": "автоматизация маркетинга"},
        nodes=[
            node("search", "web_search", "Новости ниши", query="{{niche}} тренды", period="w"),
            prompt("post", "Текст поста", "Напиши пост для LinkedIn по самой важной новости недели в нише «{{niche}}»: крючок, 3 мысли, вопрос к аудитории. До 1200 символов.",
                   instructions="Тон — экспертный, дружелюбный. Без хэштег-спама: максимум 3 хэштега."),
            node("publish", "linkedin", "Публикация", text="", visibility="PUBLIC"),
        ],
        links=[("search", "post"), ("post", "publish")],
    ),
    Template(
        slug="content-plan-to-sheets",
        category="content",
        name="Контент-план на неделю в таблицу",
        description="ИИ придумывает 7 идей постов по вашей теме и добавляет их строками в Google Таблицу.",
        name_en="Weekly content plan to a sheet",
        description_en="AI comes up with 7 post ideas for your topic and appends them as rows to Google Sheets.",
        variables={"topic": "кофейня у дома", "audience": "жители района, 25–45 лет"},
        nodes=[
            prompt("plan", "Идеи постов", "Составь контент-план на 7 дней для темы «{{topic}}», аудитория: {{audience}}.",
                   output_format='{\n  "rows": [\n    { "day": "Пн", "format": "пост/сторис/видео", "topic": "…", "hook": "…" }\n  ]\n}'),
            node("sheet", "google_sheets", "Google Таблица", operation="append", spreadsheet_id="", sheet_range="План!A1:D",
                 values_json="{{$rows}}"),
        ],
        links=[("plan", "sheet")],
    ),
    Template(
        slug="image-of-the-day",
        category="content",
        name="Картинка дня с подписью",
        description="ИИ придумывает идею и подпись, генерирует изображение и отправляет его в Telegram с текстом.",
        name_en="Picture of the day with a caption",
        description_en="AI invents an idea and a caption, generates an image and sends it to Telegram.",
        variables={"brand": "Ayakun", "style": "яркая плоская иллюстрация"},
        nodes=[
            prompt("idea", "Идея и подпись", "Придумай идею картинки для соцсетей бренда {{brand}} в стиле «{{style}}» и короткую подпись к ней.",
                   output_format='{ "image_prompt": "…", "caption": "…" }',
                   assignments=assign(caption="{{$caption}}")),
            node("draw", "image_generation", "Генерация", prompt="{{$image_prompt}}"),
            node("send", "telegram_send", "В Telegram", message="{{caption}}"),
        ],
        links=[("idea", "draw"), ("draw", "send")],
    ),
    Template(
        slug="podcast-summary-email",
        category="content",
        name="Конспект подкаста на почту",
        description="Расшифровывает аудио по ссылке, делает конспект с главными мыслями и цитатами и отправляет письмом.",
        name_en="Podcast summary by email",
        description_en="Transcribes audio from a link, writes a summary and emails it.",
        variables={"audio_url": "https://example.com/episode.mp3", "report_email": "me@example.com"},
        nodes=[
            node("audio", "audio_transcription", "Расшифровка", source="url", url="{{audio_url}}", prompt=""),
            prompt("summary", "Конспект", "Сделай конспект выпуска: 5–7 главных мыслей и 3 цитаты. Исходный текст — ниже."),
            node("mail", "email", "Письмо", to="{{report_email}}", subject="Конспект подкаста", body="{{$text}}"),
        ],
        links=[("audio", "summary"), ("summary", "mail")],
    ),
    Template(
        slug="brand-mentions-slack",
        category="content",
        name="Упоминания бренда в Slack",
        description="Ищет свежие упоминания бренда, ИИ оценивает тональность, сводка уходит в канал Slack.",
        name_en="Brand mentions to Slack",
        description_en="Searches fresh brand mentions, AI rates sentiment, the summary goes to a Slack channel.",
        variables={"brand": "Ayakun"},
        nodes=[
            node("search", "web_search", "Упоминания", query="\"{{brand}}\" отзывы", period="d"),
            node("fields", "data_transform", "Заголовки и ссылки", operation="select", fields="title, url, snippet"),
            prompt("tone", "Тональность", "Оцени тональность каждого упоминания бренда {{brand}}: позитив / нейтрально / негатив. Выведи список и общий вывод."),
            node("slack", "slack", "Канал #marketing", channel="#marketing", message="Упоминания {{brand}} за сутки:\n{{$text}}"),
        ],
        links=[("search", "fields"), ("fields", "tone"), ("tone", "slack")],
    ),

    # ── Продажи и заявки ───────────────────────────────────────────────
    Template(
        slug="lead-to-sheets-telegram",
        category="sales",
        name="Заявка с сайта → таблица и Telegram",
        description="Вебхук принимает заявку, данные приводятся к единому виду, строка добавляется в таблицу, менеджер получает сообщение.",
        name_en="Website lead → sheet and Telegram",
        description_en="A webhook receives a lead, fields are normalized, a row is added to a sheet and the manager gets a message.",
        nodes=[
            node("hook", "webhook", "Заявка с сайта"),
            node("lead", "data_transform", "Поля заявки", operation="map", path="body",
                 mapping_json='{\n  "name": "{{$name}}",\n  "phone": "{{$phone}}",\n  "email": "{{$email}}",\n  "comment": "{{$message}}"\n}',
                 assignments=assign(lead_name="{{$name}}", lead_phone="{{$phone}}")),
            node("sheet", "google_sheets", "Лиды", operation="append", spreadsheet_id="", sheet_range="Лиды!A1:D", values_json=""),
            node("notify", "telegram_send", "Менеджеру", message="Новая заявка: {{lead_name}}, {{lead_phone}}"),
        ],
        links=[("hook", "lead"), ("lead", "sheet"), ("sheet", "notify")],
    ),
    Template(
        slug="lead-scoring-reply",
        category="sales",
        name="Оценка лида ИИ и ответ клиенту",
        description="ИИ оценивает заявку от 1 до 10. Горячим лидам сразу уходит персональное письмо, остальные — в Telegram на ручную проверку.",
        name_en="AI lead scoring and reply",
        description_en="AI scores the lead 1–10. Hot leads get a personal email right away, the rest go to Telegram for review.",
        variables={"company": "Ваша компания", "hot_score": "7"},
        nodes=[
            node("hook", "webhook", "Заявка"),
            node("lead", "data_transform", "Поля заявки", operation="select", path="body", fields="name, email, message",
                 assignments=assign(lead_name="{{$name}}", lead_email="{{$email}}")),
            prompt("score", "Оценка ИИ", "Оцени заявку клиента для компании {{company}} по шкале 1–10 и напиши короткий вежливый ответ клиенту по имени.",
                   output_format='{ "score": 8, "reason": "…", "reply": "…" }',
                   assignments=assign(reply_text="{{$reply}}", lead_score="{{$score}}")),
            node("hot", "if_else", "Горячий лид?", condition="{{$score}} >= {{hot_score}}"),
            node("mail", "email", "Ответ клиенту", to="{{lead_email}}", subject="{{lead_name}}, спасибо за заявку", body="{{reply_text}}"),
            node("review", "telegram_send", "На проверку", message="Лид {{lead_name}} ({{lead_email}}) — оценка {{lead_score}}. Нужна ручная проверка."),
        ],
        links=[("hook", "lead"), ("lead", "score"), ("score", "hot"), ("hot", "mail", "true"), ("hot", "review", "false")],
    ),
    Template(
        slug="lead-to-trello-slack",
        category="sales",
        name="Заявка → карточка Trello → Slack",
        description="Каждая заявка становится карточкой на доске продаж, а команда получает ссылку на неё в Slack.",
        name_en="Lead → Trello card → Slack",
        description_en="Each lead becomes a card on the sales board and the team gets its link in Slack.",
        nodes=[
            node("hook", "webhook", "Заявка"),
            node("card", "trello", "Карточка в «Новые»", operation="create_card", list_id="",
                 name="{{$body.name}} — {{$body.phone}}", description="Комментарий: {{$body.message}}\nИсточник: сайт"),
            node("slack", "slack", "#sales", channel="#sales", message="Новая заявка на доске: {{$card.name}}\n{{$card.url}}"),
        ],
        links=[("hook", "card"), ("card", "slack")],
    ),
    Template(
        slug="crm-deals-to-excel",
        category="sales",
        name="Новые сделки из CRM в Excel",
        description="Забирает новые сделки из API вашей CRM, оставляет нужные поля и добавляет строки в таблицу Excel в OneDrive.",
        name_en="New CRM deals to Excel",
        description_en="Pulls new deals from your CRM API, keeps the needed fields and appends rows to an Excel table in OneDrive.",
        nodes=[
            node("crm", "http_request", "Сделки из CRM",
                 request_json='{\n  "method": "GET",\n  "url": "https://api.your-crm.example/deals",\n  "params": { "status": "new", "limit": 50 }\n}'),
            node("rows", "data_transform", "Нужные поля", operation="map", path="deals",
                 mapping_json='{\n  "id": "{{$id}}",\n  "client": "{{$client.name}}",\n  "amount": "{{$amount}}",\n  "stage": "{{$stage}}"\n}'),
            node("excel", "excel", "Таблица «Сделки»", operation="append", file_path="/CRM/deals.xlsx", worksheet="Sheet1", table="Deals", values_json=""),
        ],
        links=[("crm", "rows"), ("rows", "excel")],
    ),
    Template(
        slug="abandoned-carts-report",
        category="sales",
        name="Брошенные корзины — письмо менеджеру",
        description="Раз в час проверяет базу. Если есть корзины без оплаты дольше 2 часов, менеджер получает список.",
        name_en="Abandoned carts report",
        description_en="Checks the database hourly. If carts stay unpaid for 2+ hours, the manager gets a list.",
        variables={"manager_email": "sales@example.com"},
        nodes=[
            node("carts", "sql_query", "Брошенные корзины", engine="postgresql", dsn="",
                 query="SELECT id, customer_email, total, updated_at\nFROM carts\nWHERE status = 'open' AND updated_at < now() - interval '2 hours'\nORDER BY total DESC\nLIMIT 50"),
            node("any", "if_else", "Есть корзины?", condition="{{$row_count}} > 0"),
            node("mail", "email", "Менеджеру", to="{{manager_email}}", subject="Брошенные корзины: {{$passthrough.row_count}}",
                 body="{% for cart in $passthrough.rows %}• {{cart.customer_email}} — {{cart.total}} ₽\n{% endfor %}"),
        ],
        links=[("carts", "any"), ("any", "mail", "true")],
    ),
    Template(
        slug="client-profile-merge",
        category="sales",
        name="Профиль клиента из CRM и магазина",
        description="По событию с сайта параллельно берёт карточку из CRM и историю заказов из магазина, объединяет их в один профиль и готовит персональное предложение.",
        name_en="Client profile from CRM and shop",
        description_en="On a website event fetches the CRM card and order history in parallel, merges them into one profile and drafts a personal offer.",
        nodes=[
            node("hook", "webhook", "Клиент на сайте"),
            node("client", "data_transform", "Email и имя", operation="select", path="body", fields="email, name",
                 assignments=assign(client_email="{{$email}}", client_name="{{$name}}")),
            node("crm", "http_request", "Карточка в CRM",
                 request_json='{\n  "method": "GET",\n  "url": "https://api.your-crm.example/clients",\n  "params": { "email": "{{$email}}" }\n}'),
            node("orders", "http_request", "Заказы в магазине",
                 request_json='{\n  "method": "GET",\n  "url": "https://api.your-shop.example/orders",\n  "params": { "email": "{{$email}}", "limit": 20 }\n}'),
            node("merge", "data_transform", "Один профиль", operation="merge", mapping_json="source=site\nname={{client_name}}"),
            prompt("offer", "Персональное предложение", "По профилю клиента {{client_name}} предложи одну персональную скидку или товар и напиши короткое письмо."),
            node("mail", "email", "Письмо клиенту", to="{{client_email}}", subject="{{client_name}}, подборка для вас", body="{{$text}}"),
        ],
        links=[
            ("hook", "client"), ("client", "crm"), ("client", "orders"),
            ("crm", "merge"), ("orders", "merge"), ("merge", "offer"), ("offer", "mail"),
        ],
    ),

    # ── Операции и отчёты ──────────────────────────────────────────────
    Template(
        slug="daily-sales-report",
        category="ops",
        name="Ежедневный отчёт о продажах",
        description="Берёт продажи за вчера из базы, ИИ пишет выводы и рекомендации, отчёт уходит на почту.",
        name_en="Daily sales report",
        description_en="Takes yesterday's sales from the database, AI writes insights and recommendations, the report is emailed.",
        variables={"report_email": "owner@example.com"},
        nodes=[
            node("sales", "sql_query", "Продажи за вчера", engine="postgresql", dsn="",
                 query="SELECT category, count(*) AS orders, sum(total) AS revenue\nFROM orders\nWHERE created_at::date = current_date - 1\nGROUP BY category\nORDER BY revenue DESC"),
            prompt("analysis", "Выводы ИИ", "Проанализируй продажи за вчера по категориям: что выросло, что просело, 3 рекомендации на сегодня."),
            node("mail", "email", "Отчёт на почту", to="{{report_email}}", subject="Продажи за вчера", body="{{$text}}"),
        ],
        links=[("sales", "analysis"), ("analysis", "mail")],
    ),
    Template(
        slug="weekly-report-to-disk",
        category="ops",
        name="Недельный отчёт XLSX на Яндекс Диск",
        description="Собирает заказы за неделю из базы, сохраняет их в файл Excel и загружает на Яндекс Диск.",
        name_en="Weekly XLSX report to Yandex Disk",
        description_en="Collects weekly orders from the database, saves them to an Excel file and uploads it to Yandex Disk.",
        nodes=[
            node("orders", "sql_query", "Заказы за неделю", engine="postgresql", dsn="",
                 query="SELECT id, created_at, customer, total, status\nFROM orders\nWHERE created_at > now() - interval '7 days'\nORDER BY created_at"),
            node("xlsx", "spreadsheet", "Файл XLSX", operation="write", file_format="xlsx", path="rows", filename="orders-week.xlsx", sheet="Заказы"),
            node("disk", "yandex_disk", "На Яндекс Диск", operation="upload", token="", remote_path="/Отчёты/orders-week.xlsx"),
        ],
        links=[("orders", "xlsx"), ("xlsx", "disk")],
    ),
    Template(
        slug="low-stock-alert",
        category="ops",
        name="Закупщику — когда товар заканчивается",
        description="Раз в час проверяет остатки. Если что-то ниже минимума, закупщик получает письмо со списком позиций.",
        name_en="Low stock alert for the buyer",
        description_en="Checks stock hourly. If anything is below the minimum, the buyer gets an email with the list.",
        variables={"min_qty": "10", "buyer_email": "buyer@example.com"},
        nodes=[
            node("stock", "sql_query", "Остатки", engine="postgresql", dsn="",
                 query="SELECT sku, name, qty FROM stock WHERE qty < {{min_qty}} ORDER BY qty"),
            node("low", "if_else", "Есть дефицит?", condition="{{$row_count}} > 0"),
            node("mail", "email", "Закупщику", to="{{buyer_email}}", subject="Заканчиваются товары",
                 body="Ниже минимума ({{min_qty}} шт.):\n{% for item in $passthrough.rows %}• {{item.sku}} {{item.name}} — {{item.qty}} шт.\n{% endfor %}"),
        ],
        links=[("stock", "low"), ("low", "mail", "true")],
    ),
    Template(
        slug="invoice-to-disk",
        category="ops",
        name="Счёт с компьютера → Яндекс Диск",
        description="Загрузите файл счёта — цепочка сохранит его в папку на Яндекс Диске и сообщит в Telegram.",
        name_en="Invoice from your computer → Yandex Disk",
        description_en="Upload an invoice file — the workflow saves it to a Yandex Disk folder and notifies you in Telegram.",
        nodes=[
            node("file", "file", "Файл счёта", filename="", file_base64=""),
            node("disk", "yandex_disk", "Папка «Счета»", operation="upload", token="", remote_path="/Счета/{{$filename}}"),
            node("notify", "telegram_send", "Уведомление", message="Счёт сохранён: {{$remote_path}}"),
        ],
        links=[("file", "disk"), ("disk", "notify")],
    ),
    Template(
        slug="csv-import-to-sheets",
        category="ops",
        name="Импорт CSV в Google Таблицы",
        description="Загрузите CSV-выгрузку: цепочка прочитает строки, оставит только оплаченные и допишет их в Google Таблицу.",
        name_en="CSV import to Google Sheets",
        description_en="Upload a CSV export: the workflow reads rows, keeps paid ones and appends them to Google Sheets.",
        nodes=[
            node("file", "file", "CSV-выгрузка", filename="", file_base64=""),
            node("table", "spreadsheet", "Строки CSV", operation="read", file_format="csv", header_row=True),
            node("paid", "data_transform", "Только оплаченные", operation="filter", path="rows", condition='{{$status}} == "paid"'),
            node("sheet", "google_sheets", "Таблица «Оплаты»", operation="append", spreadsheet_id="", sheet_range="Оплаты!A1:Z", values_json=""),
        ],
        links=[("file", "table"), ("table", "paid"), ("paid", "sheet")],
    ),
    Template(
        slug="price-list-to-excel",
        category="ops",
        name="Прайс с Яндекс Диска в Excel",
        description="Скачивает прайс-лист с Яндекс Диска, сортирует позиции по цене и добавляет их в таблицу Excel.",
        name_en="Price list from Yandex Disk to Excel",
        description_en="Downloads a price list from Yandex Disk, sorts items by price and appends them to an Excel table.",
        nodes=[
            node("disk", "yandex_disk", "Прайс с Диска", operation="download", token="", remote_path="/Прайсы/price.xlsx"),
            node("table", "spreadsheet", "Строки прайса", operation="read", file_format="auto", header_row=True),
            node("sorted", "data_transform", "По цене", operation="sort", path="rows", sort_field="price", sort_direction="asc"),
            node("excel", "excel", "Таблица «Прайс»", operation="append", file_path="/Прайсы/Каталог.xlsx", worksheet="Sheet1", table="Prices", values_json=""),
        ],
        links=[("disk", "table"), ("table", "sorted"), ("sorted", "excel")],
    ),
    Template(
        slug="site-health-check",
        category="monitoring",
        name="Проверка сайта с повтором",
        description="Проверяет адрес сайта. Если он не отвечает, ждёт минуту, проверяет ещё раз и только тогда бьёт тревогу.",
        name_en="Website health check with retry",
        description_en="Checks your website. If it fails, waits a minute, rechecks and only then raises an alert.",
        variables={"site_url": "https://example.com/health"},
        nodes=[
            node("check", "http_request", "Проверка", request_json='{\n  "method": "GET",\n  "url": "{{site_url}}"\n}'),
            node("down", "if_else", "Не отвечает?", condition='{{$status}} != "ok"'),
            node("wait", "delay", "Пауза 1 мин", amount="1", unit="minutes"),
            node("recheck", "http_request", "Повторная проверка", request_json='{\n  "method": "GET",\n  "url": "{{site_url}}"\n}'),
            node("still", "if_else", "Всё ещё лежит?", condition='{{$status}} != "ok"'),
            node("alert", "telegram_send", "Тревога", message="🔴 {{site_url}} не отвечает уже больше минуты"),
        ],
        links=[("check", "down"), ("down", "wait", "true"), ("wait", "recheck"), ("recheck", "still"), ("still", "alert", "true")],
    ),

    # ── Мониторинг ─────────────────────────────────────────────────────
    Template(
        slug="usd-rate-alert",
        category="monitoring",
        name="Курс доллара выше порога",
        description="Берёт официальный курс ЦБ и пишет в Telegram, только если доллар дороже заданного порога.",
        name_en="USD rate above a threshold",
        description_en="Gets the official Central Bank rate and writes to Telegram only when USD exceeds your threshold.",
        variables={"usd_threshold": "95"},
        nodes=[
            node("rate", "http_request", "Курс ЦБ", request_json='{\n  "method": "GET",\n  "url": "https://www.cbr-xml-daily.ru/daily_json.js"\n}',
                 assignments=assign(usd="{{$Valute.USD.Value}}")),
            node("high", "if_else", "Выше порога?", condition="{{$Valute.USD.Value}} > {{usd_threshold}}"),
            node("send", "telegram_send", "В Telegram", message="Доллар по ЦБ: {{usd}} ₽ — выше порога {{usd_threshold}} ₽"),
        ],
        links=[("rate", "high"), ("high", "send", "true")],
    ),
    Template(
        slug="vacancies-digest",
        category="monitoring",
        name="Подборка вакансий в Telegram",
        description="Ищет свежие вакансии, ИИ отбирает подходящие под ваши требования и присылает короткий список.",
        name_en="Job openings digest",
        description_en="Searches fresh job openings, AI picks the relevant ones and sends a short list.",
        variables={"position": "Python-разработчик", "requirements": "удалённо, от 250 000 ₽"},
        nodes=[
            node("search", "web_search", "Вакансии", query="вакансия {{position}} {{requirements}}", period="d"),
            prompt("pick", "Отбор ИИ", "Отбери до 7 вакансий, подходящих под требования: {{requirements}}. Для каждой — компания, зарплата и ссылка."),
            node("send", "telegram_send", "В Telegram", message=""),
        ],
        links=[("search", "pick"), ("pick", "send")],
    ),
    Template(
        slug="competitor-price-watch",
        category="monitoring",
        name="Цена конкурента ниже порога",
        description="Проверяет цену товара конкурента через API и пишет письмо, если она опустилась ниже вашей.",
        name_en="Competitor price watch",
        description_en="Checks a competitor's product price via API and emails you if it drops below yours.",
        variables={"my_price": "4990", "alert_email": "pricing@example.com"},
        nodes=[
            node("price", "http_request", "Цена конкурента",
                 request_json='{\n  "method": "GET",\n  "url": "https://api.competitor.example/products/12345"\n}'),
            node("pick", "data_transform", "Цена и название", operation="select", fields="name, price, url"),
            node("cheaper", "if_else", "Дешевле нашей?", condition="{{$price}} < {{my_price}}"),
            node("mail", "email", "Письмо", to="{{alert_email}}", subject="Конкурент снизил цену",
                 body="{{$passthrough.name}}: {{$passthrough.price}} ₽ (наша — {{my_price}} ₽)\n{{$passthrough.url}}"),
        ],
        links=[("price", "pick"), ("pick", "cheaper"), ("cheaper", "mail", "true")],
    ),
    Template(
        slug="search-results-sheet",
        category="monitoring",
        name="Выдача поиска в таблицу",
        description="Раз в неделю собирает выдачу по вашему запросу и дописывает заголовки и ссылки в Google Таблицу — удобно следить за позициями.",
        name_en="Search results to a sheet",
        description_en="Weekly collects search results for your query and appends titles and links to Google Sheets.",
        variables={"query": "конструктор автоматизаций с ИИ"},
        nodes=[
            node("search", "web_search", "Выдача", query="{{query}}", period="w"),
            node("rows", "data_transform", "Заголовок и ссылка", operation="map",
                 mapping_json='{ "query": "{{query}}", "title": "{{$title}}", "url": "{{$url}}" }'),
            node("sheet", "google_sheets", "Таблица позиций", operation="append", spreadsheet_id="", sheet_range="Выдача!A1:C", values_json=""),
        ],
        links=[("search", "rows"), ("rows", "sheet")],
    ),

    # ── Разработка и задачи ────────────────────────────────────────────
    Template(
        slug="bug-report-to-jira",
        category="dev",
        name="Баг-репорт с сайта → задача в Jira",
        description="Форма обратной связи шлёт вебхук, ИИ оформляет задачу с приоритетом, она создаётся в Jira, а команда видит её в Slack.",
        name_en="Bug report → Jira issue",
        description_en="A feedback form sends a webhook, AI formats the issue with priority, it is created in Jira and posted to Slack.",
        variables={"jira_project": "SUP"},
        nodes=[
            node("hook", "webhook", "Форма обратной связи"),
            prompt("format", "Оформление задачи", "Оформи баг-репорт пользователя в задачу: заголовок, шаги воспроизведения, ожидаемое и фактическое поведение.",
                   output_format='{ "summary": "…", "description": "…" }'),
            node("issue", "jira", "Задача в Jira", operation="create_issue", base_url="", email="", api_token="",
                 project_key="{{jira_project}}", issue_type="Bug", summary="{{$summary}}", description="{{$description}}"),
            node("slack", "slack", "#dev", channel="#dev", message="Новый баг {{$key}}: {{$summary}}\n{{$url}}"),
        ],
        links=[("hook", "format"), ("format", "issue"), ("issue", "slack")],
    ),
    Template(
        slug="jira-standup-slack",
        category="dev",
        name="Сводка для стендапа из Jira",
        description="Каждое утро берёт открытые задачи спринта, ИИ группирует их по статусам и присылает сводку в Slack.",
        name_en="Standup summary from Jira",
        description_en="Every morning takes open sprint issues, AI groups them by status and posts a summary to Slack.",
        nodes=[
            node("issues", "jira", "Задачи спринта", operation="search", base_url="", email="", api_token="",
                 jql="sprint in openSprints() AND status != Done ORDER BY priority DESC"),
            prompt("standup", "Сводка", "Сгруппируй задачи по статусам и исполнителям. Отдельно отметь заблокированные и просроченные. Коротко, для стендапа."),
            node("slack", "slack", "#standup", channel="#standup", message=""),
        ],
        links=[("issues", "standup"), ("standup", "slack")],
    ),
    Template(
        slug="trello-deadlines",
        category="dev",
        name="Дедлайны карточек Trello",
        description="Собирает карточки списка «В работе», оставляет те, у которых есть срок, и присылает напоминание в Telegram.",
        name_en="Trello deadlines reminder",
        description_en="Collects cards from the “In progress” list, keeps those with a due date and sends a Telegram reminder.",
        nodes=[
            node("cards", "trello", "Карточки «В работе»", operation="list_cards", list_id=""),
            node("due", "data_transform", "Со сроком", operation="filter", path="cards", condition="{{$due}}"),
            node("sorted", "data_transform", "По сроку", operation="sort", sort_field="due", sort_direction="asc"),
            node("send", "telegram_send", "Напоминание", message="Сроки по карточкам:\n{% for card in $ %}• {{card.name}} — до {{card.due}}\n{% endfor %}"),
        ],
        links=[("cards", "due"), ("due", "sorted"), ("sorted", "send")],
    ),
    Template(
        slug="release-notes-slack",
        category="dev",
        name="Заметки о релизе из коммитов",
        description="Берёт последние коммиты репозитория на GitHub, ИИ пишет понятные заметки о релизе и публикует их в Slack.",
        name_en="Release notes from commits",
        description_en="Takes the latest GitHub commits, AI writes readable release notes and posts them to Slack.",
        variables={"repo": "owner/repository"},
        nodes=[
            node("commits", "http_request", "Коммиты GitHub",
                 request_json='{\n  "method": "GET",\n  "url": "https://api.github.com/repos/{{repo}}/commits",\n  "params": { "per_page": 20 }\n}'),
            node("messages", "data_transform", "Сообщения коммитов", operation="map",
                 mapping_json='{ "message": "{{$commit.message}}", "author": "{{$commit.author.name}}" }'),
            prompt("notes", "Заметки о релизе", "Сгруппируй изменения: новое, исправления, улучшения. Пиши для пользователей, без технического жаргона."),
            node("slack", "slack", "#releases", channel="#releases", message=""),
        ],
        links=[("commits", "messages"), ("messages", "notes"), ("notes", "slack")],
    ),
    Template(
        slug="meeting-minutes-tasks",
        category="dev",
        name="Протокол встречи и список задач",
        description="Расшифровывает запись встречи, ИИ выделяет задачи с ответственными, цикл собирает список, итог уходит письмом участникам.",
        name_en="Meeting minutes and tasks",
        description_en="Transcribes a meeting, AI extracts tasks with owners, a loop builds the list and it is emailed to attendees.",
        variables={"recording_url": "https://example.com/meeting.mp3", "team_email": "team@example.com"},
        nodes=[
            node("audio", "audio_transcription", "Запись встречи", source="url", url="{{recording_url}}", prompt=""),
            prompt("tasks", "Задачи и решения", "Выдели из расшифровки встречи решения и задачи с ответственными и сроками.",
                   output_format='{\n  "summary": "…",\n  "tasks": [ { "title": "…", "owner": "…", "due": "…" } ]\n}',
                   assignments=assign(meeting_summary="{{$summary}}")),
            node("loop", "loop", "По задачам", mode="for_each", source="$tasks"),
            node("mail", "email", "Протокол участникам", to="{{team_email}}", subject="Протокол встречи",
                 body="{{meeting_summary}}\n\nЗадачи:\n{% for task in $items %}• {{task.title}} — {{task.owner}}, до {{task.due}}\n{% endfor %}"),
        ],
        links=[("audio", "tasks"), ("tasks", "loop"), ("loop", "mail")],
    ),

    # ── ИИ и медиа ─────────────────────────────────────────────────────
    Template(
        slug="receipt-to-excel",
        category="media",
        name="Чек по фото → таблица расходов",
        description="Распознаёт фото чека, достаёт дату, магазин и сумму и добавляет строку в таблицу расходов Excel.",
        name_en="Receipt photo → expenses table",
        description_en="Recognizes a receipt photo, extracts date, shop and total and adds a row to an Excel expenses table.",
        variables={"receipt_url": "https://example.com/receipt.jpg"},
        nodes=[
            node("photo", "image", "Фото чека", source="url", url="{{receipt_url}}"),
            node("read", "image_recognition", "Распознавание",
                 prompt='Это кассовый чек. Верни только JSON: { "date": "ГГГГ-ММ-ДД", "shop": "…", "total": 0 }'),
            node("row", "data_transform", "Строка расходов", operation="set", mapping_json="category=Продукты"),
            node("excel", "excel", "Таблица «Расходы»", operation="append", file_path="/Финансы/Расходы.xlsx", worksheet="Sheet1", table="Expenses", values_json=""),
        ],
        links=[("photo", "read"), ("read", "row"), ("row", "excel")],
    ),
    Template(
        slug="photo-description",
        category="media",
        name="Описание фото товара",
        description="Смотрит на фото товара и пишет продающее описание и alt-текст — сразу в Telegram.",
        name_en="Product photo description",
        description_en="Looks at a product photo and writes a selling description and alt text — straight to Telegram.",
        variables={"photo_url": "https://example.com/product.jpg"},
        nodes=[
            node("photo", "image", "Фото товара", source="url", url="{{photo_url}}"),
            node("read", "image_recognition", "Описание по фото",
                 prompt="Опиши товар на фото для карточки маркетплейса: 3 преимущества, материалы, для кого. Отдельной строкой — alt-текст до 120 символов."),
            node("send", "telegram_send", "В Telegram", message=""),
        ],
        links=[("photo", "read"), ("read", "send")],
    ),
    # ── Подборки для опроса после регистрации: работают без внешних ключей ──
    Template(
        slug="telegram-channel-post",
        category="content",
        name="Готовый пост для канала",
        description="Находит свежий повод в вашей теме, ИИ пишет пост для Telegram-канала и присылает его вам на проверку.",
        name_en="Ready-made channel post",
        description_en="Finds a fresh topic in your niche, AI writes a Telegram channel post and sends it to you for review.",
        variables={"topic": "маркетинг для малого бизнеса", "tone": "дружелюбный и экспертный"},
        nodes=[
            node("search", "web_search", "Свежие поводы", query="{{topic}} новости", period="d"),
            prompt("post", "Текст поста", "Выбери самую интересную новость по теме «{{topic}}» и напиши пост для Telegram-канала: цепляющий заголовок, суть в 3–4 абзацах, вывод для читателя. До 1000 символов.",
                   instructions="Тон — {{tone}}. Уместные эмодзи, без хэштегов."),
            node("send", "telegram_send", "Черновик в Telegram", message=""),
        ],
        links=[("search", "post"), ("post", "send")],
    ),
    Template(
        slug="competitor-news-digest",
        category="monitoring",
        name="Что нового у конкурентов",
        description="Ищет свежие упоминания конкурентов в сети, ИИ выделяет запуски, акции и изменения цен и присылает сводку.",
        name_en="Competitor news digest",
        description_en="Searches fresh mentions of competitors, AI highlights launches, promotions and price changes and sends a summary.",
        variables={"competitors": "Конкурент 1, Конкурент 2"},
        nodes=[
            node("search", "web_search", "Упоминания конкурентов", query="{{competitors}} новости акции", period="w"),
            prompt("digest", "Сводка по конкурентам", "Сделай сводку о конкурентах ({{competitors}}): новые продукты, акции, цены, заметные публикации. Для каждого пункта — вывод, что это значит для нас, и ссылка.",
                   instructions="Коротко, списком, без воды."),
            node("send", "telegram_send", "В Telegram", message=""),
        ],
        links=[("search", "digest"), ("digest", "send")],
    ),
    Template(
        slug="tenders-digest",
        category="sales",
        name="Подборка тендеров и заказов",
        description="Ищет новые тендеры и запросы на ваши услуги, ИИ отбирает подходящие и присылает список со ссылками.",
        name_en="Tenders and orders digest",
        description_en="Searches new tenders and requests for your services, AI picks the relevant ones and sends a list with links.",
        variables={"service": "разработка сайтов", "region": "Москва"},
        nodes=[
            node("search", "web_search", "Тендеры и запросы", query="тендер закупка {{service}} {{region}}", period="d"),
            prompt("pick", "Отбор ИИ", "Отбери до 7 тендеров или запросов, подходящих под услугу «{{service}}» в регионе {{region}}. Для каждого — заказчик, суть, бюджет (если есть), срок и ссылка."),
            node("send", "telegram_send", "В Telegram", message=""),
        ],
        links=[("search", "pick"), ("pick", "send")],
    ),
    Template(
        slug="client-research",
        category="sales",
        name="Досье на клиента перед встречей",
        description="Собирает свежие новости о компании клиента, ИИ готовит короткое досье и идеи для разговора.",
        name_en="Client brief before a meeting",
        description_en="Collects fresh news about the client's company, AI prepares a short brief and talking points.",
        variables={"company": "ООО «Ромашка»"},
        nodes=[
            node("search", "web_search", "Новости о компании", query="{{company}} новости", period="m"),
            prompt("brief", "Досье", "Подготовь досье на компанию {{company}} перед встречей: чем занимается, последние новости, возможные боли и 3 идеи, с чего начать разговор."),
            node("send", "telegram_send", "В Telegram", message=""),
        ],
        links=[("search", "brief"), ("brief", "send")],
    ),
    Template(
        slug="competitor-prices-digest",
        category="monitoring",
        name="Цены конкурентов на товар",
        description="Ищет предложения по вашему товару в интернет-магазинах и на маркетплейсах, ИИ сравнивает цены с вашей.",
        name_en="Competitor prices for a product",
        description_en="Searches offers for your product in online shops and marketplaces, AI compares prices with yours.",
        variables={"product": "беспроводные наушники", "my_price": "4990"},
        nodes=[
            node("search", "web_search", "Предложения", query="{{product}} купить цена", period="w"),
            prompt("compare", "Сравнение цен", "Найди в результатах цены на товар «{{product}}» и сравни с нашей ценой {{my_price}} ₽: кто дешевле, кто дороже, средняя цена рынка и рекомендация."),
            node("send", "telegram_send", "В Telegram", message=""),
        ],
        links=[("search", "compare"), ("compare", "send")],
    ),
    Template(
        slug="reviews-digest",
        category="monitoring",
        name="Разбор отзывов о товаре",
        description="Собирает свежие отзывы о товаре или бренде, ИИ выделяет частые жалобы и похвалы и предлагает улучшения.",
        name_en="Product reviews analysis",
        description_en="Collects fresh reviews of a product or brand, AI highlights frequent complaints and praise and suggests improvements.",
        variables={"product": "ваш товар или бренд"},
        nodes=[
            node("search", "web_search", "Свежие отзывы", query="{{product}} отзывы", period="w"),
            prompt("analysis", "Анализ отзывов", "Проанализируй отзывы о «{{product}}»: 3 частые жалобы, 3 за что хвалят, общий тон и 3 конкретных улучшения."),
            node("send", "telegram_send", "В Telegram", message=""),
        ],
        links=[("search", "analysis"), ("analysis", "send")],
    ),
    Template(
        slug="tech-news-digest",
        category="dev",
        name="Новости вашего стека",
        description="Ищет релизы, уязвимости и статьи по технологиям, с которыми вы работаете, и присылает короткую выжимку.",
        name_en="Your tech stack news",
        description_en="Searches releases, vulnerabilities and articles on the technologies you use and sends a short summary.",
        variables={"stack": "Python, FastAPI, PostgreSQL"},
        nodes=[
            node("search", "web_search", "Релизы и статьи", query="{{stack}} release news", period="w"),
            prompt("digest", "Выжимка", "Сделай выжимку новостей по стеку {{stack}}: новые версии, важные изменения, уязвимости, интересные статьи. Для каждого пункта — одна фраза и ссылка.",
                   instructions="Пиши по-русски, коротко, для разработчиков."),
            node("send", "telegram_send", "В Telegram", message=""),
        ],
        links=[("search", "digest"), ("digest", "send")],
    ),
    Template(
        slug="business-law-digest",
        category="monitoring",
        name="Изменения в законах для бизнеса",
        description="Следит за новыми законами, налогами и требованиями в вашей сфере, ИИ объясняет, что нужно сделать.",
        name_en="Law changes for business",
        description_en="Tracks new laws, taxes and requirements in your field, AI explains what you need to do.",
        variables={"industry": "розничная торговля"},
        nodes=[
            node("search", "web_search", "Новые требования", query="изменения закон налог {{industry}} бизнес", period="w"),
            prompt("explain", "Что это значит", "Выдели изменения в законах, налогах и требованиях для сферы «{{industry}}». Для каждого: что меняется, с какой даты, что нужно сделать бизнесу, ссылка на источник."),
            node("send", "telegram_send", "В Telegram", message=""),
        ],
        links=[("search", "explain"), ("explain", "send")],
    ),
    Template(
        slug="currency-rates-daily",
        category="monitoring",
        name="Курсы валют с комментарием",
        description="Берёт официальные курсы ЦБ, ИИ коротко описывает изменения к прошлому дню и присылает сводку.",
        name_en="Currency rates with commentary",
        description_en="Takes the official Central Bank rates, AI briefly describes the change since yesterday and sends a summary.",
        variables={"currencies": "USD, EUR, CNY"},
        nodes=[
            node("rates", "http_request", "Курсы ЦБ", request_json='{\n  "method": "GET",\n  "url": "https://www.cbr-xml-daily.ru/daily_json.js"\n}'),
            prompt("summary", "Сводка", "По данным ЦБ дай курсы {{currencies}}: текущее значение (Value), изменение к предыдущему (Previous) в рублях и процентах. В конце — одна фраза общего вывода.",
                   instructions="Коротко, списком, со стрелками ↑ ↓."),
            node("send", "telegram_send", "В Telegram", message=""),
        ],
        links=[("rates", "summary"), ("summary", "send")],
    ),
    Template(
        slug="daily-lesson",
        category="content",
        name="Урок дня",
        description="ИИ каждый раз готовит короткий урок по выбранной теме: новое слово, правило или приём с примером и мини-заданием.",
        name_en="Lesson of the day",
        description_en="AI prepares a short lesson on your topic each time: a new word, rule or technique with an example and a mini task.",
        variables={"subject": "английский язык", "level": "средний"},
        nodes=[
            prompt("lesson", "Урок", "Подготовь короткий урок по теме «{{subject}}» для уровня «{{level}}»: одно новое понятие или слово, объяснение простыми словами, 2 примера и мини-задание. Каждый раз выбирай новое.",
                   instructions="Дружелюбно, не длиннее 800 символов."),
            node("send", "telegram_send", "В Telegram", message=""),
        ],
        links=[("lesson", "send")],
    ),
    Template(
        slug="city-events-digest",
        category="content",
        name="Афиша событий в городе",
        description="Ищет концерты, выставки и мероприятия в вашем городе, ИИ отбирает интересные под ваши увлечения.",
        name_en="City events digest",
        description_en="Searches concerts, exhibitions and events in your city, AI picks those matching your interests.",
        variables={"city": "Москва", "interests": "выставки, стендап, джаз"},
        nodes=[
            node("search", "web_search", "Афиша", query="афиша {{city}} мероприятия {{interests}}", period="w"),
            prompt("pick", "Подборка", "Отбери до 7 событий в городе {{city}} под интересы: {{interests}}. Для каждого — название, дата, место и ссылка."),
            node("send", "telegram_send", "В Telegram", message=""),
        ],
        links=[("search", "pick"), ("pick", "send")],
    ),
]

BY_SLUG = {item.slug: item for item in TEMPLATES}


def get_template(slug: str) -> Template:
    template = BY_SLUG.get(slug)
    if template is None:
        raise HTTPException(404, "Шаблон не найден")
    return template


async def use_template(
    db: AsyncSession,
    user: User,
    slug: str,
    *,
    mobile: bool = False,
    schedule_slots: list[ScheduleSlot] | None = None,
    schedule_timezone: str = "UTC",
    search_period: SearchPeriod | None = None,
) -> Workflow:
    """Копирует шаблон в цепочки пользователя: все узлы, связи и переменные.

    mobile — открыть в мобильном редакторе (только линейные шаблоны); search_period подстраивает
    глубину поиска под частоту запуска, чтобы ежедневная цепочка не присылала недельные новости.
    """
    from services.billing import BillingService
    from services.workflow import WorkflowService

    template = get_template(slug)
    if mobile and not template.linear():
        raise HTTPException(422, "В шаблоне есть ветвления — откройте его с компьютера")
    raw = template.graph()
    if search_period is not None:
        for item in raw["nodes"]:
            if item["type"] == "web_search":
                item["period"] = search_period.value
    if mobile:
        for index, item in enumerate(raw["nodes"]):
            item["position"] = {"x": 0, "y": index * ROW_HEIGHT}
    graph = WorkflowGraph.model_validate(raw)
    data = WorkflowCreate(
        name=template.name,
        description=template.description,
        graph=graph,
        variables=dict(template.variables),
        mobile=mobile,
        schedule_slots=schedule_slots or None,
        schedule_timezone=schedule_timezone,
    )
    return await WorkflowService(db, BillingService(db)).create(data, user)
