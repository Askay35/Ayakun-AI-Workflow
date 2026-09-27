"""CRUD и жизненный цикл workflow: черновик → publish → run (в очередь Celery)."""

from __future__ import annotations

import json
import logging
import secrets
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from core.config import settings
from models.workflow import (
    NodeRun,
    NodeRunStatus,
    RunStatus,
    Workflow,
    WorkflowRun,
    WorkflowStatus,
    WorkflowVersion,
)
from models.user import AuthIdentity, IdentityProvider, User
from schemas.workflow import (
    AudioTranscriptionNode,
    Bitrix24Node,
    DataTransformNode,
    DelayNode,
    EmailNode,
    ExcelNode,
    FileNode,
    GoogleSheetsNode,
    ImageGenerationNode,
    ImageNode,
    ImageRecognitionNode,
    JiraNode,
    LinkedInNode,
    LoopNode,
    NodeType,
    RunStepResponse,
    ScheduleSlot,
    SlackNode,
    SpreadsheetNode,
    SqlQueryNode,
    TelegramSendNode,
    TrelloNode,
    WeeklyScheduleSlot,
    WorkflowCreate,
    WorkflowGraph,
    WorkflowNode,
    WorkflowUpdate,
    YandexDiskNode,
)
from helper import display_telegram_output
from services.billing import BillingService
from services.billing.subscriptions import SubscriptionService
from services.stored_images import (
    consume_image_node_budget,
    image_node_ids,
    storage_quota_message,
    strip_stored_images,
    uploaded_images,
)
from services.pricing import PricingService
from services.schedule import (
    derived_cron,
    dump_slots,
    earliest_next,
    load_slots,
    prepare_slots,
    slots_from_legacy,
)

logger = logging.getLogger(__name__)


def topological_nodes(graph: WorkflowGraph):
    """Обход узлов в порядке зависимостей: сначала родители, потом дети."""
    by_id = {node.id: node for node in graph.nodes}
    indegree = {node.id: len(node.parents) for node in graph.nodes}
    queue = [node_id for node_id, degree in indegree.items() if degree == 0]
    while queue:
        node_id = queue.pop(0)
        yield by_id[node_id]
        for child_id in by_id[node_id].children:
            if child_id not in indegree:
                continue
            indegree[child_id] -= 1
            if indegree[child_id] == 0:
                queue.append(child_id)


def _validate_request_json(node_id: str, request_json: str, errors: list[str]) -> None:
    try:
        parsed = json.loads(request_json)
    except json.JSONDecodeError as exc:
        errors.append(f"Узел {node_id}: некорректный JSON в данных запроса ({exc.msg})")
        return
    if not isinstance(parsed, dict):
        errors.append(f"Узел {node_id}: данные запроса должны быть JSON-объектом")
        return
    if "url" not in parsed:
        errors.append(f"Узел {node_id}: в данных запроса нет поля url")


def _single_incoming_label(node_type: NodeType) -> str:
    return {
        NodeType.TELEGRAM_SEND: "Telegram",
        NodeType.HTTP_REQUEST: "HTTP Request",
        NodeType.IF_ELSE: "IF ELSE",
        NodeType.GOOGLE_SHEETS: "Google Таблицы",
        NodeType.EMAIL: "Email",
        NodeType.DATA_TRANSFORM: "Преобразование",
        NodeType.SQL_QUERY: "База данных",
        NodeType.LOOP: "Цикл",
        NodeType.DELAY: "Задержка",
        NodeType.YANDEX_DISK: "Яндекс Диск",
        NodeType.IMAGE_GENERATION: "Генерация изображения",
        NodeType.IMAGE: "Изображение",
        NodeType.IMAGE_RECOGNITION: "Распознавание изображения",
        NodeType.AUDIO_TRANSCRIPTION: "Расшифровка аудио",
        NodeType.SLACK: "Slack",
        NodeType.TRELLO: "Trello",
        NodeType.JIRA: "Jira",
        NodeType.EXCEL: "Excel",
        NodeType.FILE: "Файл",
        NodeType.SPREADSHEET: "Таблица",
        NodeType.LINKEDIN: "LinkedIn",
        NodeType.BITRIX24: "Битрикс24",
    }.get(node_type, node_type.value)


def _validate_node_config(node: WorkflowNode, errors: list[str]) -> None:
    label = node.label or node.id
    if node.type == NodeType.WEB_SEARCH and not node.query.strip():
        errors.append(f"Узел {label}: укажите поисковый запрос")
    elif node.type == NodeType.PROMPT and not node.prompt.strip():
        errors.append(f"Узел {label}: укажите промпт")
    elif node.type == NodeType.HTTP_REQUEST:
        if not node.request_json.strip():
            errors.append(f"Узел {label}: укажите данные запроса")
    elif node.type == NodeType.IF_ELSE:
        if not node.condition.strip():
            errors.append(f"Узел {label}: укажите условие IF ELSE")
        if not node.true_children and not node.false_children:
            errors.append(f"Узел {label}: подключите ветку TRUE или FALSE")
        overlap = set(node.true_children) & set(node.false_children)
        if overlap:
            errors.append(f"Узел {label}: TRUE и FALSE не могут вести в один узел")
    elif isinstance(node, TelegramSendNode):
        if node.uses_custom_bot() and node.chat_id_blank():
            errors.append(f"Узел {label}: укажите chat_id для отправки через своего бота")
    elif isinstance(node, GoogleSheetsNode):
        if not node.spreadsheet_id.strip():
            errors.append(f"Узел {label}: укажите идентификатор таблицы")
        has_write_auth = bool(node.access_token.strip() or node.service_account_json.strip())
        has_any_auth = has_write_auth or bool(node.api_key.strip())
        if not has_any_auth:
            errors.append(f"Узел {label}: укажите токен Google, API-ключ или JSON сервисного аккаунта")
        elif node.operation != "read" and not has_write_auth:
            errors.append(f"Узел {label}: для записи нужен токен Google или JSON сервисного аккаунта")
    elif isinstance(node, EmailNode):
        if not node.to.strip():
            errors.append(f"Узел {label}: укажите получателя письма")
    elif isinstance(node, DataTransformNode):
        if node.operation in {"select", "remove"} and not node.fields.strip():
            errors.append(f"Узел {label}: укажите поля")
        elif node.operation in {"rename", "set", "map"} and not node.mapping_json.strip():
            errors.append(f"Узел {label}: укажите соответствие полей или шаблон")
        elif node.operation == "filter" and not node.condition.strip():
            errors.append(f"Узел {label}: укажите условие Filter")
        elif node.operation == "sort" and not node.sort_field.strip():
            errors.append(f"Узел {label}: укажите поле сортировки")
    elif isinstance(node, SqlQueryNode):
        if not node.dsn.strip():
            errors.append(f"Узел {label}: укажите строку подключения")
        if not node.query.strip():
            errors.append(f"Узел {label}: укажите SQL-запрос")
    elif isinstance(node, LoopNode):
        if node.mode == "for_each" and not node.source.strip():
            errors.append(f"Узел {label}: укажите источник массива")
        elif node.mode == "times" and not node.times.strip():
            errors.append(f"Узел {label}: укажите число повторов")
        elif node.mode == "while":
            if not node.while_variable.strip():
                errors.append(f"Узел {label}: выберите переменную цикла")
            if not node.while_value.strip():
                errors.append(f"Узел {label}: укажите значение сравнения")
    elif isinstance(node, DelayNode):
        if not node.amount.strip():
            errors.append(f"Узел {label}: укажите длительность")
    elif isinstance(node, YandexDiskNode):
        if not node.token.strip():
            errors.append(f"Узел {label}: укажите токен Яндекс Диска")
        if not node.remote_path.strip():
            errors.append(f"Узел {label}: укажите путь на Яндекс Диске")
    elif isinstance(node, ImageGenerationNode):
        if not node.prompt.strip():
            errors.append(f"Узел {label}: укажите промпт")
    elif isinstance(node, ImageNode):
        if node.source == "url" and not node.url.strip():
            errors.append(f"Узел {label}: укажите ссылку на изображение")
        elif node.source == "file" and not node.file_base64.strip():
            errors.append(f"Узел {label}: загрузите файл изображения")
        elif node.source == "upstream" and not node.parents:
            errors.append(f"Узел {label}: подключите предыдущий узел")
    elif isinstance(node, ImageRecognitionNode):
        if not node.prompt.strip():
            errors.append(f"Узел {label}: укажите промпт")
    elif isinstance(node, AudioTranscriptionNode):
        if node.source == "url" and not node.url.strip():
            errors.append(f"Узел {label}: укажите ссылку на аудио")
        elif node.source == "file" and not node.file_base64.strip():
            errors.append(f"Узел {label}: загрузите аудиофайл")
        elif node.source == "upstream" and not node.parents:
            errors.append(f"Узел {label}: подключите предыдущий узел")
    elif isinstance(node, SlackNode):
        if not node.webhook_url.strip() and not (node.bot_token.strip() and node.channel.strip()):
            errors.append(f"Узел {label}: укажите вебхук Slack или токен бота и канал")
    elif isinstance(node, TrelloNode):
        if not node.api_key.strip() or not node.token.strip():
            errors.append(f"Узел {label}: укажите API-ключ и токен Trello")
        if node.operation in {"create_card", "list_cards", "move_card"} and not node.list_id.strip():
            errors.append(f"Узел {label}: укажите список Trello")
        if node.operation in {"move_card", "add_comment"} and not node.card_id.strip():
            errors.append(f"Узел {label}: укажите карточку Trello")
        if node.operation == "create_card" and not node.name.strip():
            errors.append(f"Узел {label}: укажите название карточки")
        if node.operation == "add_comment" and not node.description.strip():
            errors.append(f"Узел {label}: укажите текст комментария")
    elif isinstance(node, JiraNode):
        if not node.base_url.strip() or not node.email.strip() or not node.api_token.strip():
            errors.append(f"Узел {label}: укажите адрес Jira, email и API-токен")
        if node.operation == "create_issue" and (not node.project_key.strip() or not node.summary.strip()):
            errors.append(f"Узел {label}: укажите проект и заголовок задачи")
        elif node.operation == "search" and not node.jql.strip():
            errors.append(f"Узел {label}: укажите JQL-запрос")
        elif node.operation == "add_comment" and (not node.issue_key.strip() or not node.comment.strip()):
            errors.append(f"Узел {label}: укажите ключ задачи и комментарий")
    elif isinstance(node, Bitrix24Node):
        if not node.webhook_url.strip():
            errors.append(f"Узел {label}: укажите адрес вебхука Битрикс24")
        if node.operation in {"update", "get", "delete"} and not node.item_id.strip():
            errors.append(f"Узел {label}: укажите ID элемента Битрикс24")
        if node.operation in {"create", "update"} and not node.fields_json.strip():
            errors.append(f"Узел {label}: укажите поля элемента (JSON)")
    elif isinstance(node, ExcelNode):
        if not node.access_token.strip():
            errors.append(f"Узел {label}: укажите токен Microsoft")
        if not node.file_path.strip():
            errors.append(f"Узел {label}: укажите путь к книге Excel")
        if node.operation == "append" and not node.table.strip():
            errors.append(f"Узел {label}: укажите имя таблицы для добавления строк")
        elif node.operation == "update" and not node.cell_range.strip():
            errors.append(f"Узел {label}: укажите диапазон для обновления")
    elif isinstance(node, FileNode):
        if not node.file_base64.strip():
            errors.append(f"Узел {label}: загрузите файл")
    elif isinstance(node, SpreadsheetNode):
        if node.operation == "read" and not node.parents:
            errors.append(f"Узел {label}: подключите узел «Файл» или «Яндекс Диск»")
    elif isinstance(node, LinkedInNode):
        if not node.access_token.strip() or not node.author.strip():
            errors.append(f"Узел {label}: укажите токен LinkedIn и автора")


def _allows_many_parents(node: WorkflowNode) -> bool:
    """Merge собирает данные из нескольких веток, поэтому ему можно несколько входов."""
    return isinstance(node, DataTransformNode) and node.operation == "merge"


def _validate_image_recognition_parents(node: WorkflowNode, by_id: dict, errors: list[str], *, strict: bool) -> None:
    if len(node.parents) > 1 or (strict and len(node.parents) != 1):
        errors.append(f"Узел {node.label}: распознавание изображения должно иметь ровно одну входящую связь")
        return
    if len(node.parents) != 1:
        return
    parent = by_id.get(node.parents[0])
    if parent is not None and parent.type != NodeType.IMAGE:
        errors.append(f"Узел {node.label}: распознавание изображения должно идти сразу после узла «Изображение»")


def validate_graph(graph: WorkflowGraph, *, strict: bool = False) -> list[str]:
    """Проверка графа. strict=True — перед публикацией/валидацией в UI (полный набор правил)."""
    errors: list[str] = []
    ids = [node.id for node in graph.nodes]
    if strict and not ids:
        errors.append("Граф не может быть пустым")
    if len(ids) != len(set(ids)):
        errors.append("ID узлов должны быть уникальны")
    by_id = {node.id: node for node in graph.nodes}
    known = set(ids)
    indegree = {node_id: 0 for node_id in ids}
    if sum(1 for node in graph.nodes if node.type == NodeType.WEBHOOK) > 1:
        errors.append("В цепочке может быть только один вебхук")
    extra_single = NodeType.single_incoming() - {
        NodeType.HTTP_REQUEST,
        NodeType.IF_ELSE,
        NodeType.TELEGRAM_SEND,
        NodeType.IMAGE_RECOGNITION,
    }
    if strict:
        for node in graph.nodes:
            _validate_node_config(node, errors)
            if node.type == NodeType.HTTP_REQUEST:
                if len(node.parents) > 1:
                    errors.append(f"Узел {node.label}: HTTP Request может иметь только одну входящую связь")
                elif len(node.parents) == 1 and node.parents[0] in by_id and by_id[node.parents[0]].type not in NodeType.with_output():
                    errors.append(f"Узел {node.label}: родитель HTTP Request должен быть узлом с выводом")
            elif node.type == NodeType.IF_ELSE:
                if len(node.parents) != 1:
                    errors.append(f"Узел {node.label}: IF ELSE должен иметь ровно одну входящую связь")
                elif node.parents[0] in by_id and by_id[node.parents[0]].type not in NodeType.with_output():
                    errors.append(f"Узел {node.label}: родитель IF ELSE должен быть узлом с выводом")
            elif node.type == NodeType.IMAGE_RECOGNITION:
                _validate_image_recognition_parents(node, by_id, errors, strict=True)
            elif node.type in extra_single and not _allows_many_parents(node):
                if len(node.parents) > 1:
                    errors.append(f"Узел {node.label}: {_single_incoming_label(node.type)} может иметь только одну входящую связь")
                elif len(node.parents) == 1 and node.parents[0] in by_id and by_id[node.parents[0]].type not in NodeType.with_output():
                    errors.append(f"Узел {node.label}: родитель должен быть узлом с выводом")
    for node in graph.nodes:
        for parent_id in node.parents:
            if parent_id not in known:
                errors.append(f"Узел {node.label}: неизвестный родитель {parent_id}")
            elif parent_id == node.id:
                errors.append(f"Узел {node.label}: не может ссылаться на себя")
        for child_id in node.children:
            if child_id not in known:
                errors.append(f"Узел {node.label}: неизвестный потомок {child_id}")
        indegree[node.id] = len(node.parents)
        if node.type == NodeType.WEBHOOK and node.parents:
            errors.append(f"Узел {node.label}: вебхук должен быть стартовым узлом")
        if node.type == NodeType.HTTP_REQUEST:
            if node.request_json.strip():
                _validate_request_json(node.id, node.request_json, errors)
            if not strict and len(node.parents) > 1:
                errors.append(f"Узел {node.label}: HTTP Request может иметь только одну входящую связь")
        if node.type == NodeType.IF_ELSE:
            if not strict and len(node.parents) > 1:
                errors.append(f"Узел {node.label}: IF ELSE может иметь только одну входящую связь")
        if node.type in extra_single and not strict and len(node.parents) > 1 and not _allows_many_parents(node):
            errors.append(f"Узел {node.label}: {_single_incoming_label(node.type)} может иметь только одну входящую связь")
        if node.type == NodeType.IMAGE_RECOGNITION and not strict:
            _validate_image_recognition_parents(node, by_id, errors, strict=False)
        if node.type == NodeType.TELEGRAM_SEND:
            if len(node.parents) > 1:
                errors.append(f"Узел {node.label}: Telegram может иметь только одну входящую связь")
            elif len(node.parents) == 1:
                parent = by_id.get(node.parents[0])
                if parent is not None and parent.type not in NodeType.with_output():
                    errors.append(f"Узел {node.label}: родитель Telegram должен быть узлом с текстовым выводом")
    queue = [node_id for node_id, degree in indegree.items() if degree == 0]
    if strict and ids and len(queue) != 1:
        errors.append("Опубликованный граф должен иметь ровно один стартовый узел")
    visited = 0
    remaining = dict(indegree)
    while queue:
        current = queue.pop()
        visited += 1
        for child_id in by_id[current].children:
            if child_id not in remaining:
                continue
            remaining[child_id] -= 1
            if remaining[child_id] == 0:
                queue.append(child_id)
    if ids and visited != len(ids):
        errors.append("Граф должен быть DAG")
    return errors


MOBILE_BLOCKED_TYPES = frozenset({NodeType.IF_ELSE, NodeType.LOOP})


def validate_mobile_graph(graph: WorkflowGraph) -> list[str]:
    """Мобильная цепочка — простой список шагов: один вход, один выход, без ветвлений."""
    errors: list[str] = []
    for node in graph.nodes:
        if node.type in MOBILE_BLOCKED_TYPES:
            errors.append(f"Узел {node.label}: условия и циклы доступны только в редакторе на компьютере")
        if len(node.parents) > 1 or len(node.children) > 1:
            errors.append(f"Узел {node.label}: в мобильной цепочке у шага один вход и один выход")
    if len([node for node in graph.nodes if not node.parents]) > 1:
        errors.append("Мобильная цепочка должна быть одним списком шагов")
    return errors


def incoming_slots(data: WorkflowCreate | WorkflowUpdate) -> tuple[list[ScheduleSlot] | None, bool | None]:
    if "schedule_slots" in data.model_fields_set:
        return list(data.schedule_slots or []), data.schedule_enabled
    if "schedule" in data.model_fields_set:
        if data.schedule is None:
            return [], False
        return [WeeklyScheduleSlot(time=data.schedule.time, weekdays=data.schedule.weekdays)], True
    if getattr(data, "schedule_cron", None) and "schedule_cron" in data.model_fields_set:
        return slots_from_legacy(data.schedule_cron), data.schedule_enabled
    return None, data.schedule_enabled if "schedule_enabled" in data.model_fields_set else None


def ensure_webhook_token(workflow: Workflow, graph: WorkflowGraph, *, rotate: bool = False) -> None:
    if rotate:
        workflow.webhook_token = secrets.token_urlsafe(32)
        return
    if any(node.type == NodeType.WEBHOOK for node in graph.nodes) and not workflow.webhook_token:
        workflow.webhook_token = secrets.token_urlsafe(32)


def apply_workflow_schedule(
    workflow,
    *,
    slots: list[ScheduleSlot] | None,
    enabled: bool | None,
    timezone: str | None = None,
) -> None:
    if timezone:
        workflow.schedule_timezone = timezone
    current = load_slots(workflow.schedule_slots) or slots_from_legacy(workflow.schedule_cron)
    resolved = current if slots is None else slots
    is_enabled = bool(resolved) if enabled is None else bool(enabled) and bool(resolved)
    prepared = prepare_slots(resolved, workflow.schedule_timezone, enabled=is_enabled, previous=current)
    workflow.schedule_slots = dump_slots(prepared)
    workflow.schedule_cron = derived_cron(prepared, is_enabled)
    workflow.next_run_at = earliest_next(prepared) if is_enabled else None


def solo_graph_for_node(node: WorkflowNode) -> WorkflowGraph:
    """Копия узла без родителей/детей — для одиночного запуска из черновика."""
    payload = node.model_dump(mode="json")
    payload["parents"] = []
    payload["children"] = []
    if payload.get("type") == NodeType.IF_ELSE.value:
        payload["true_children"] = []
        payload["false_children"] = []
    return WorkflowGraph.model_validate({"nodes": [payload]})


def validate_solo_node(node: WorkflowNode) -> list[str]:
    errors: list[str] = []
    blocked = settings.solo_run_blocked_types()
    node_type = node.type.value if isinstance(node.type, NodeType) else str(node.type)
    if node_type in blocked:
        errors.append(f"Узел типа {node_type} нельзя запускать отдельно")
        return errors
    if node.type == NodeType.WEB_SEARCH and not node.query.strip():
        errors.append("Укажите поисковый запрос")
    elif node.type == NodeType.PROMPT and not node.prompt.strip():
        errors.append("Укажите промпт")
    elif node.type == NodeType.HTTP_REQUEST:
        if not node.request_json.strip():
            errors.append("Укажите данные запроса")
        else:
            _validate_request_json(node.id, node.request_json, errors)
    else:
        _validate_node_config(node, errors)
        errors[:] = [item.split(": ", 1)[-1] if ": " in item else item for item in errors]
    return errors


class WorkflowService:
    def __init__(self, db: AsyncSession, billing: BillingService | None = None, redis_client=None):
        self.db = db
        self.billing = billing
        self.redis = redis_client

    async def _owned(self, workflow_id: uuid.UUID, user: User) -> Workflow:
        workflow = await self.db.scalar(select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == user.id))
        if not workflow:
            raise HTTPException(404, "Workflow не найден")
        return workflow

    async def create(self, data: WorkflowCreate, user: User) -> Workflow:
        if self.billing:
            # Стартовые токены и пробный период выдаются при первом обращении к кошельку.
            await self.billing.ensure_initial_credit(user)
        await SubscriptionService(self.db).require_active(user.id)
        workflows_count = await self.db.scalar(select(func.count(Workflow.id)).where(Workflow.owner_id == user.id))
        if workflows_count >= settings.max_workflows_count:
            raise HTTPException(400, "Вы достигли максимального количества workflows")
        errors = validate_graph(data.graph)
        if data.mobile:
            errors += validate_mobile_graph(data.graph)
        if errors:
            raise HTTPException(422, errors)
        await self._guard_image_uploads(user, data.graph, previous=None, replace_id=None)
        workflow = Workflow(
            owner_id=user.id,
            name=data.name,
            description=data.description,
            draft_graph=data.graph.model_dump(mode="json"),
            schedule_timezone=data.schedule_timezone,
            estimated_run_cost=await PricingService(self.db).estimate_graph(data.graph),
            variables=dict(data.variables or data.graph.variables or {}),
            mobile=data.mobile,
        )
        slots, enabled = incoming_slots(data)
        apply_workflow_schedule(
            workflow,
            slots=slots or [],
            enabled=True if enabled is None and slots else enabled,
            timezone=data.schedule_timezone,
        )
        ensure_webhook_token(workflow, data.graph)
        self.db.add(workflow)
        await self.db.commit()
        return workflow

    async def list(self, user: User) -> list[Workflow]:
        result = await self.db.scalars(select(Workflow).where(Workflow.owner_id == user.id).order_by(Workflow.created_at.desc()))
        return list(result)

    async def get(self, workflow_id: uuid.UUID, user: User) -> Workflow:
        return await self._owned(workflow_id, user)

    async def update(self, workflow_id: uuid.UUID, data: WorkflowUpdate, user: User) -> Workflow:
        """Сохраняет черновик (draft_graph). Опубликованная версия не меняется, пока не publish."""
        workflow = await self._owned(workflow_id, user)
        values = data.model_dump(
            exclude_unset=True,
            exclude={"graph", "schedule", "schedule_slots", "schedule_enabled", "schedule_cron", "rotate_webhook_token"},
        )
        graph = WorkflowGraph.model_validate(workflow.draft_graph or {"nodes": []})
        if "graph" in data.model_fields_set and data.graph is not None:
            previous = graph
            graph = data.graph
            errors = validate_graph(graph)
            if workflow.mobile:
                errors += validate_mobile_graph(graph)
            if errors:
                raise HTTPException(422, errors)
            await self._guard_image_uploads(user, graph, previous=previous, replace_id=workflow.id)
            workflow.draft_graph = graph.model_dump(mode="json")
            workflow.estimated_run_cost = await PricingService(self.db).estimate_graph(graph)
        for key, value in values.items():
            setattr(workflow, key, value)
        ensure_webhook_token(workflow, graph, rotate=bool(data.rotate_webhook_token))
        slots, enabled = incoming_slots(data)
        if slots is not None or enabled is not None or "schedule_timezone" in data.model_fields_set:
            apply_workflow_schedule(
                workflow,
                slots=slots,
                enabled=enabled,
                timezone=data.schedule_timezone,
            )
        await self.db.commit()
        return workflow

    async def delete(self, workflow_id: uuid.UUID, user: User) -> None:
        """Удаление цепочки убирает черновик и снимки, а с ними и загруженные картинки."""
        workflow = await self._owned(workflow_id, user)
        await self.db.delete(workflow)
        await self.db.commit()

    async def _guard_image_uploads(self, user: User, graph: WorkflowGraph, *, previous: WorkflowGraph | None, replace_id: uuid.UUID | None) -> None:
        old_ids = image_node_ids(previous) if previous is not None else set()
        added = len(image_node_ids(graph) - old_ids)
        await consume_image_node_budget(self.redis, user.id, added)
        if previous is not None and sorted(uploaded_images(graph)) == sorted(uploaded_images(previous)):
            return
        files, nbytes = await self._image_usage(user.id, graph, replace_id)
        limits = await SubscriptionService(self.db).storage_limits(user.id)
        if files <= limits.max_files and nbytes <= limits.max_bytes:
            return
        if previous is not None:
            # Лимит уже превышен (например, тариф закончился): убирать файлы можно, добавлять — нет.
            old_files, old_bytes = await self._image_usage(user.id, previous, replace_id)
            if files <= old_files and nbytes <= old_bytes:
                return
        await SubscriptionService(self.db).require_active(user.id)
        raise HTTPException(422, storage_quota_message(limits.max_files, limits.max_bytes))

    async def storage_usage(self, user: User) -> tuple[int, int]:
        return await self._image_usage(user.id, WorkflowGraph(nodes=[]), None)

    async def _image_usage(self, user_id: int, incoming: WorkflowGraph, replace_id: uuid.UUID | None) -> tuple[int, int]:
        files = 0
        nbytes = 0
        workflows = list(await self.db.scalars(select(Workflow).where(Workflow.owner_id == user_id)))
        for workflow in workflows:
            draft = incoming if replace_id is not None and workflow.id == replace_id else WorkflowGraph.model_validate(workflow.draft_graph or {"nodes": []})
            seen = {node_id for node_id, _size in uploaded_images(draft)}
            for _node_id, size in uploaded_images(draft):
                files += 1
                nbytes += size
            if not workflow.published_version_id:
                continue
            version = await self.db.get(WorkflowVersion, workflow.published_version_id)
            snapshot = version.graph_snapshot if version else None
            for node_id, size in uploaded_images(snapshot if isinstance(snapshot, dict) else {}):
                if node_id in seen:
                    continue
                files += 1
                nbytes += size
        if replace_id is None:
            for _node_id, size in uploaded_images(incoming):
                files += 1
                nbytes += size
        return files, nbytes

    async def _drop_replaced_image_bytes(self, workflow_id: uuid.UUID, keep_version_id: uuid.UUID) -> None:
        """После публикации байты картинок остаются только в новом снимке и черновике."""
        versions = list(await self.db.scalars(select(WorkflowVersion).where(WorkflowVersion.workflow_id == workflow_id)))
        for version in versions:
            if version.id == keep_version_id:
                continue
            snapshot = version.graph_snapshot
            if isinstance(snapshot, dict) and strip_stored_images(snapshot):
                version.graph_snapshot = snapshot
                flag_modified(version, "graph_snapshot")

    async def validate(self, workflow_id: uuid.UUID, user: User) -> list[str]:
        workflow = await self._owned(workflow_id, user)
        graph = WorkflowGraph.model_validate(workflow.draft_graph)
        errors = validate_graph(graph, strict=True)
        return errors + validate_mobile_graph(graph) if workflow.mobile else errors

    async def publish(self, workflow_id: uuid.UUID, user: User) -> Workflow:
        """Фиксирует снимок draft_graph в WorkflowVersion — дальше runs идут по этому снимку."""
        workflow = await self._owned(workflow_id, user)
        graph = WorkflowGraph.model_validate(workflow.draft_graph)
        graph.variables = dict(workflow.variables or {})
        errors = validate_graph(graph, strict=True)
        if workflow.mobile:
            errors += validate_mobile_graph(graph)
        # chat_id в узле можно не указывать, если у пользователя привязан Telegram.
        if any(
            isinstance(node, TelegramSendNode)
            and not node.uses_custom_bot()
            and node.chat_id_blank()
            for node in graph.nodes
        ):
            has_telegram = await self.db.scalar(
                select(AuthIdentity.id).where(
                    AuthIdentity.user_id == user.id,
                    AuthIdentity.provider == IdentityProvider.telegram,
                )
            )
            if not has_telegram:
                errors.append("Для telegram_send необходимо привязать Telegram")
        if errors:
            raise HTTPException(422, errors)
        snapshot = graph.model_dump(mode="json")
        workflow.draft_graph = snapshot
        ensure_webhook_token(workflow, graph)
        number = (await self.db.scalar(select(func.max(WorkflowVersion.version)).where(
            WorkflowVersion.workflow_id == workflow.id
        )) or 0) + 1
        version = WorkflowVersion(workflow_id=workflow.id, version=number, graph_snapshot=snapshot)
        self.db.add(version)
        await self.db.flush()
        await self._drop_replaced_image_bytes(workflow.id, version.id)
        workflow.published_version_id = version.id
        workflow.status = WorkflowStatus.published
        await self.db.commit()
        return workflow

    async def run(self, workflow_id: uuid.UUID, user: User, input_data: dict) -> WorkflowRun:
        """Создаёт WorkflowRun и кладёт задачу в Celery; исполнение — на worker."""
        workflow = await self._owned(workflow_id, user)
        await SubscriptionService(self.db).require_active(user.id)
        if not workflow.published_version_id:
            raise HTTPException(409, "Workflow не опубликован")
        version = await self.db.get(WorkflowVersion, workflow.published_version_id)
        graph = WorkflowGraph.model_validate(version.graph_snapshot if version else {"nodes": []})
        if self.billing:
            wallet = await self.billing.ensure_initial_credit(user)
            estimate = await PricingService(self.db).estimate_graph(graph)
            available = wallet.balance - wallet.reserved
            if available < estimate:
                raise HTTPException(402, "Недостаточно credits для запуска")
        run = WorkflowRun(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            workflow_version_id=workflow.published_version_id,
            owner_id=user.id,
            input=input_data,
        )
        run.workflow = workflow
        self.db.add(run)
        await self.db.flush()
        if self.billing:
            await self.billing.reserve_run(user, run.id, f"run:{run.id}", amount=estimate)
        else:
            await self.db.commit()
        from execution.tasks import execute_workflow
        execute_workflow.delay(str(run.id))
        logger.info(
            "Задача выполнения поставлена в очередь",
            extra={
                "event": "run.queued",
                "run_id": str(run.id),
                "workflow_id": str(workflow.id),
                "owner_id": user.id,
            },
        )
        return run

    async def trigger_webhook(self, token: str, payload: dict) -> WorkflowRun:
        workflow = await self.db.scalar(select(Workflow).where(Workflow.webhook_token == token))
        if not workflow or workflow.status != WorkflowStatus.published or not workflow.published_version_id:
            raise HTTPException(404, "Вебхук не найден")
        version = await self.db.get(WorkflowVersion, workflow.published_version_id)
        graph = WorkflowGraph.model_validate(version.graph_snapshot if version else {"nodes": []})
        if not any(node.type == NodeType.WEBHOOK for node in graph.nodes):
            raise HTTPException(404, "Вебхук не найден")
        owner = await self.db.get(User, workflow.owner_id)
        if owner is None:
            raise HTTPException(404, "Вебхук не найден")
        return await self.run(workflow.id, owner, payload)

    async def run_node(
        self,
        workflow_id: uuid.UUID,
        node_id: str,
        user: User,
        input_data: dict | None = None,
    ) -> WorkflowRun:
        """Запускает один узел из текущего черновика, без публикации всей цепочки."""
        workflow = await self._owned(workflow_id, user)
        await SubscriptionService(self.db).require_active(user.id)
        graph = WorkflowGraph.model_validate(workflow.draft_graph or {"nodes": []})
        graph.variables = dict(workflow.variables or {})
        node = next((item for item in graph.nodes if item.id == node_id), None)
        if node is None:
            raise HTTPException(404, "Узел не найден")
        errors = validate_solo_node(node)
        if isinstance(node, TelegramSendNode) and not node.uses_custom_bot() and node.chat_id_blank():
            has_telegram = await self.db.scalar(
                select(AuthIdentity.id).where(
                    AuthIdentity.user_id == user.id,
                    AuthIdentity.provider == IdentityProvider.telegram,
                )
            )
            if not has_telegram:
                errors.append("Для telegram_send необходимо привязать Telegram или указать chat_id")
        if errors:
            raise HTTPException(422, errors)
        solo_graph = solo_graph_for_node(node)
        solo_graph.variables = dict(workflow.variables or {})
        if self.billing:
            wallet = await self.billing.ensure_initial_credit(user)
            estimate = await PricingService(self.db).estimate_graph(solo_graph)
            available = wallet.balance - wallet.reserved
            if available < estimate:
                raise HTTPException(402, "Недостаточно credits для запуска")
        else:
            estimate = await PricingService(self.db).estimate_graph(solo_graph)
        number = (await self.db.scalar(select(func.max(WorkflowVersion.version)).where(
            WorkflowVersion.workflow_id == workflow.id
        )) or 0) + 1
        version = WorkflowVersion(
            workflow_id=workflow.id,
            version=number,
            graph_snapshot=solo_graph.model_dump(mode="json"),
        )
        self.db.add(version)
        await self.db.flush()
        payload = dict(input_data or {})
        payload["_solo"] = True
        payload["_solo_node_id"] = node.id
        payload["_solo_node_type"] = node.type.value
        run = WorkflowRun(
            id=uuid.uuid4(),
            workflow_id=workflow.id,
            workflow_version_id=version.id,
            owner_id=user.id,
            input=payload,
        )
        run.workflow = workflow
        self.db.add(run)
        await self.db.flush()
        if self.billing:
            await self.billing.reserve_run(user, run.id, f"run:{run.id}", amount=estimate)
        else:
            await self.db.commit()
        from execution.tasks import execute_workflow
        execute_workflow.delay(str(run.id))
        logger.info(
            "Одиночный запуск узла поставлен в очередь",
            extra={
                "event": "run.queued",
                "run_id": str(run.id),
                "workflow_id": str(workflow.id),
                "owner_id": user.id,
                "node_id": node.id,
                "node_type": node.type.value,
                "solo": True,
            },
        )
        return run

    async def get_run(self, run_id: uuid.UUID, user: User) -> WorkflowRun:
        run = await self.db.scalar(
            select(WorkflowRun)
            .options(selectinload(WorkflowRun.workflow))
            .where(WorkflowRun.id == run_id, WorkflowRun.owner_id == user.id)
        )
        if not run:
            raise HTTPException(404, "Run не найден")
        return run

    async def list_runs(self, user: User) -> list[WorkflowRun]:
        result = await self.db.scalars(
            select(WorkflowRun)
            .options(selectinload(WorkflowRun.workflow))
            .where(WorkflowRun.owner_id == user.id)
            .order_by(WorkflowRun.created_at.desc())
        )
        return list(result)

    async def list_node_runs(self, run_id: uuid.UUID, user: User) -> list[NodeRun]:
        run = await self.get_run(run_id, user)
        result = await self.db.scalars(
            select(NodeRun)
            .where(NodeRun.workflow_run_id == run.id)
            .order_by(NodeRun.started_at.asc().nulls_first())
        )
        return list(result)

    async def list_run_steps(self, run_id: uuid.UUID, user: User) -> list[RunStepResponse]:
        """Шаги запуска в порядке выполнения графа: выполненные, текущий и ожидающие."""
        run = await self.get_run(run_id, user)
        version = await self.db.get(WorkflowVersion, run.workflow_version_id)
        graph = WorkflowGraph.model_validate(version.graph_snapshot if version else {"nodes": []})
        node_runs = {
            node_run.node_id: node_run
            for node_run in await self.db.scalars(
                select(NodeRun).where(NodeRun.workflow_run_id == run.id)
            )
        }
        steps: list[RunStepResponse] = []
        for node in topological_nodes(graph):
            steps.append(self._run_step(node, node_runs.pop(node.id, None)))
        # Узлы, которых уже нет в снимке, всё равно показываем в конце.
        for node_run in node_runs.values():
            step = RunStepResponse.model_validate(node_run, from_attributes=True)
            if step.node_type == NodeType.TELEGRAM_SEND.value:
                step.output = display_telegram_output(step.output)
            steps.append(step)
        return steps

    @staticmethod
    def _run_step(node: WorkflowNode, node_run: NodeRun | None) -> RunStepResponse:
        if node_run is None:
            return RunStepResponse(
                node_id=node.id,
                node_type=str(node.type.value),
                label=node.label,
                status=NodeRunStatus.pending,
            )
        output = node_run.output
        if node.type == NodeType.TELEGRAM_SEND:
            output = display_telegram_output(output)
        return RunStepResponse(
            node_id=node_run.node_id,
            node_type=str(node.type.value),
            label=node.label,
            status=node_run.status,
            attempt=node_run.attempt,
            output=output,
            error=node_run.error,
            started_at=node_run.started_at,
            finished_at=node_run.finished_at,
        )

    async def cancel(self, run_id: uuid.UUID, user: User) -> WorkflowRun:
        """Мягкая отмена: worker увидит cancel_requested между узлами и остановится."""
        run = await self.get_run(run_id, user)
        if run.status in {RunStatus.succeeded, RunStatus.failed, RunStatus.cancelled}:
            return run
        run.cancel_requested = True
        await self.db.commit()
        return run
