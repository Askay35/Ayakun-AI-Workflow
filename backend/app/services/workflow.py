"""CRUD и жизненный цикл workflow: черновик → publish → run (в очередь Celery)."""

from __future__ import annotations

import json
import logging
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
    NodeType,
    RunStepResponse,
    ScheduleSlot,
    WeeklyScheduleSlot,
    WorkflowCreate,
    WorkflowGraph,
    WorkflowNode,
    WorkflowUpdate,
)
from services.billing import BillingService
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
    if strict:
        for node in graph.nodes:
            if node.type == NodeType.WEB_SEARCH and not node.query.strip():
                errors.append(f"Узел {node.label}: укажите поисковый запрос")
            elif node.type == NodeType.PROMPT and not node.prompt.strip():
                errors.append(f"Узел {node.label}: укажите промпт")
            elif node.type == NodeType.HTTP_REQUEST:
                if not node.request_json.strip():
                    errors.append(f"Узел {node.label}: укажите данные запроса")
                if len(node.parents) > 1:
                    errors.append(f"Узел {node.label}: HTTP Request может иметь только одну входящую связь")
                elif len(node.parents) == 1 and node.parents[0] in by_id and by_id[node.parents[0]].type not in NodeType.with_output():
                    errors.append(f"Узел {node.label}: родитель HTTP Request должен быть узлом с выводом")
            elif node.type == NodeType.IF_ELSE:
                if not node.condition.strip():
                    errors.append(f"Узел {node.label}: укажите условие IF ELSE")
                if len(node.parents) != 1:
                    errors.append(f"Узел {node.label}: IF ELSE должен иметь ровно одну входящую связь")
                elif node.parents[0] in by_id and by_id[node.parents[0]].type not in NodeType.with_output():
                    errors.append(f"Узел {node.label}: родитель IF ELSE должен быть узлом с выводом")
                if not node.true_children:
                    errors.append(f"Узел {node.label}: подключите ветку TRUE")
                if not node.false_children:
                    errors.append(f"Узел {node.label}: подключите ветку FALSE")
                overlap = set(node.true_children) & set(node.false_children)
                if overlap:
                    errors.append(f"Узел {node.label}: TRUE и FALSE не могут вести в один узел")
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
        if node.type == NodeType.HTTP_REQUEST:
            if node.request_json.strip():
                _validate_request_json(node.id, node.request_json, errors)
            if not strict and len(node.parents) > 1:
                errors.append(f"Узел {node.label}: HTTP Request может иметь только одну входящую связь")
        if node.type == NodeType.IF_ELSE:
            if not strict and len(node.parents) > 1:
                errors.append(f"Узел {node.label}: IF ELSE может иметь только одну входящую связь")
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
    is_enabled = bool(resolved) if enabled is None else bool(enabled)
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
    return errors


class WorkflowService:
    def __init__(self, db: AsyncSession, billing: BillingService | None = None):
        self.db = db
        self.billing = billing

    async def _owned(self, workflow_id: uuid.UUID, user: User) -> Workflow:
        workflow = await self.db.scalar(select(Workflow).where(Workflow.id == workflow_id, Workflow.owner_id == user.id))
        if not workflow:
            raise HTTPException(404, "Workflow не найден")
        return workflow

    async def create(self, data: WorkflowCreate, user: User) -> Workflow:
        workflows_count = await self.db.scalar(select(func.count(Workflow.id)).where(Workflow.owner_id == user.id))
        if workflows_count >= settings.max_workflows_count:
            raise HTTPException(400, "Вы достигли максимального количества workflows")
        errors = validate_graph(data.graph)
        if errors:
            raise HTTPException(422, errors)
        workflow = Workflow(
            owner_id=user.id,
            name=data.name,
            description=data.description,
            draft_graph=data.graph.model_dump(mode="json"),
            schedule_timezone=data.schedule_timezone,
            estimated_run_cost=await PricingService(self.db).estimate_graph(data.graph),
            variables=dict(data.variables or data.graph.variables or {}),
        )
        slots, enabled = incoming_slots(data)
        apply_workflow_schedule(
            workflow,
            slots=slots or [],
            enabled=True if enabled is None and slots else enabled,
            timezone=data.schedule_timezone,
        )
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
            exclude={"graph", "schedule", "schedule_slots", "schedule_enabled", "schedule_cron"},
        )
        if "graph" in data.model_fields_set and data.graph is not None:
            graph = data.graph
            errors = validate_graph(graph)
            if errors:
                raise HTTPException(422, errors)
            workflow.draft_graph = graph.model_dump(mode="json")
            workflow.estimated_run_cost = await PricingService(self.db).estimate_graph(graph)
        for key, value in values.items():
            setattr(workflow, key, value)
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
        workflow = await self._owned(workflow_id, user)
        await self.db.delete(workflow)
        await self.db.commit()

    async def validate(self, workflow_id: uuid.UUID, user: User) -> list[str]:
        workflow = await self._owned(workflow_id, user)
        return validate_graph(WorkflowGraph.model_validate(workflow.draft_graph), strict=True)

    async def publish(self, workflow_id: uuid.UUID, user: User) -> Workflow:
        """Фиксирует снимок draft_graph в WorkflowVersion — дальше runs идут по этому снимку."""
        workflow = await self._owned(workflow_id, user)
        graph = WorkflowGraph.model_validate(workflow.draft_graph)
        graph.variables = dict(workflow.variables or {})
        errors = validate_graph(graph, strict=True)
        # chat_id в узле можно не указывать, если у пользователя привязан Telegram.
        if any(node.type == NodeType.TELEGRAM_SEND and node.chat_id is None for node in graph.nodes):
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
        number = (await self.db.scalar(select(func.max(WorkflowVersion.version)).where(
            WorkflowVersion.workflow_id == workflow.id
        )) or 0) + 1
        version = WorkflowVersion(workflow_id=workflow.id, version=number, graph_snapshot=snapshot)
        self.db.add(version)
        await self.db.flush()
        workflow.published_version_id = version.id
        workflow.status = WorkflowStatus.published
        await self.db.commit()
        return workflow

    async def run(self, workflow_id: uuid.UUID, user: User, input_data: dict) -> WorkflowRun:
        """Создаёт WorkflowRun и кладёт задачу в Celery; исполнение — на worker."""
        workflow = await self._owned(workflow_id, user)
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

    async def run_node(
        self,
        workflow_id: uuid.UUID,
        node_id: str,
        user: User,
        input_data: dict | None = None,
    ) -> WorkflowRun:
        """Запускает один узел из текущего черновика, без публикации всей цепочки."""
        workflow = await self._owned(workflow_id, user)
        graph = WorkflowGraph.model_validate(workflow.draft_graph or {"nodes": []})
        graph.variables = dict(workflow.variables or {})
        node = next((item for item in graph.nodes if item.id == node_id), None)
        if node is None:
            raise HTTPException(404, "Узел не найден")
        errors = validate_solo_node(node)
        if node.type == NodeType.TELEGRAM_SEND and node.chat_id is None:
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
            steps.append(RunStepResponse.model_validate(node_run, from_attributes=True))
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
        return RunStepResponse(
            node_id=node_run.node_id,
            node_type=str(node.type.value),
            label=node.label,
            status=node_run.status,
            attempt=node_run.attempt,
            output=node_run.output,
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
