"""Celery-задачи выполнения workflow.

backend только ставит задачу в RabbitMQ (execute_workflow.delay).
Реальная работа узлов идёт здесь, в процессе worker.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import uuid
from decimal import Decimal

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from core.config import settings
from execution.celery_app import celery_app
from models.user import User
from models.workflow import (
    NodeRun,
    NodeRunStatus,
    RunStatus,
    Workflow,
    WorkflowRun,
    WorkflowStatus,
    WorkflowVersion,
)
from schemas.workflow import NodeType, WorkflowGraph, WorkflowNode
from services.billing import BillingService
from services.execution import DefaultExecutors, NodeRegistry, node_type_value
from services.execution.errors import user_visible_error
from services.pricing import PricingService, billable_credits, billed_credits, provider_cost_usd
from services.schedule import advance_due_slots, dump_slots, earliest_next, load_slots, slots_from_legacy
from services.workflow import topological_nodes
from core.logging import output_preview

logger = logging.getLogger(__name__)


def task_session_factory():
    task_engine = create_async_engine(settings.db_url, poolclass=NullPool)
    return task_engine, async_sessionmaker(task_engine, expire_on_commit=False)


async def node_cost(
    pricing: PricingService,
    node: object,
    output: dict | list,
) -> tuple[Decimal, int, dict]:
    if getattr(node, "type") == NodeType.WEB_SEARCH:
        price = await pricing.get("serper", "search")
        credits = billable_credits(price.search)
        details = {"provider": "serper", "model": "search", "searches": 1}
        return credits, 0, {**details, "provider_cost_usd": str(provider_cost_usd(credits))}
    if getattr(node, "type") == NodeType.TELEGRAM_SEND:
        return Decimal("0"), 0, {"provider": "telegram", "model": "send"}
    if getattr(node, "type") == NodeType.HTTP_REQUEST:
        return Decimal("0"), 0, {"provider": "http", "model": "request"}
    if getattr(node, "type") == NodeType.IF_ELSE:
        return Decimal("0"), 0, {"provider": "if_else", "model": "branch"}
    usage = output.get("usage") if isinstance(output, dict) else {}
    usage = usage or {}
    model = output.get("model") or getattr(node, "model", None) or (
        settings.deepseek_complex_model
        if getattr(node, "complexity", "simple_text") == "complex_text"
        else settings.deepseek_simple_model
    )
    price = await pricing.get("deepseek", model)
    hit = int(usage.get("input_cache_hit_tokens", 0))
    miss = int(usage.get("input_cache_miss_tokens", 0))
    if hit + miss == 0:
        miss = int(usage.get("input_tokens", 0))
    generated = int(usage.get("output_tokens", 0))
    credits = billed_credits(price, hit, miss, generated)
    units = hit + miss + generated
    details = {
        "provider": "deepseek",
        "model": model,
        "input_cache_hit_tokens": hit,
        "input_cache_miss_tokens": miss,
        "output_tokens": generated,
        "provider_cost_usd": str(provider_cost_usd(credits)),
        "truncated": bool(output.get("truncated", False)),
    }
    return credits, units, details


def jsonable_output(output: object) -> dict | list:
    if hasattr(output, "model_dump"):
        return output.model_dump(mode="json")
    if isinstance(output, list):
        return [item.model_dump(mode="json") if hasattr(item, "model_dump") else item for item in output]
    return output


def unselected_if_else_children(node: WorkflowNode, branch: str | None) -> list[str]:
    """Потомки IF ELSE, которые не на выбранной ветке — их нельзя выполнять."""
    true_children = list(getattr(node, "true_children", None) or [])
    false_children = list(getattr(node, "false_children", None) or [])
    if branch == "true":
        chosen = set(true_children)
    elif branch == "false":
        chosen = set(false_children)
    else:
        chosen = set()
    return [child_id for child_id in node.children if child_id not in chosen]


async def release_unused_reserve(
    db: AsyncSession,
    billing: BillingService,
    user: User,
    run: WorkflowRun,
    reservation_request_id: str,
) -> None:
    await billing.release_run(user, reservation_request_id, f"release:{run.id}")


class WorkflowRunExecutor:
    def __init__(
        self,
        db: AsyncSession,
        run: WorkflowRun,
        user: User,
        graph: WorkflowGraph,
        billing: BillingService,
        reservation_request_id: str,
    ):
        self.db = db
        self.run = run
        self.user = user
        self.graph = graph
        self.billing = billing
        self.reservation_request_id = reservation_request_id
        self.pricing = PricingService(db)

    def log_fields(self, **extra) -> dict:
        return {
            "run_id": str(self.run.id),
            "workflow_id": str(self.run.workflow_id),
            "owner_id": self.run.owner_id,
            **extra,
        }

    @classmethod
    async def prepare(cls, db: AsyncSession, run_id: str) -> WorkflowRunExecutor | None:
        run = await db.scalar(select(WorkflowRun).where(WorkflowRun.id == uuid.UUID(run_id)).with_for_update())
        if not run or run.status != RunStatus.queued:
            logger.info(
                "Задача пропущена: run не в очереди",
                extra={"event": "run.skipped", "run_id": run_id, "status": getattr(run, "status", None)},
            )
            return None
        version = await db.get(WorkflowVersion, run.workflow_version_id)
        user = await db.get(User, run.owner_id)
        graph = WorkflowGraph.model_validate(version.graph_snapshot)
        billing = BillingService(db)
        await billing.ensure_initial_credit(user)
        reservation_request_id = f"run:{run.id}"
        estimate = await PricingService(db).estimate_graph(graph)
        try:
            await billing.reserve_run(user, run.id, reservation_request_id, amount=estimate)
        except HTTPException as exc:
            run.status = RunStatus.failed
            run.error = user_visible_error(exc)
            run.finished_at = datetime.datetime.now(datetime.UTC)
            await db.commit()
            logger.error(
                "Запуск не начат: не удалось зарезервировать credits",
                extra={
                    "event": "run.failed",
                    "run_id": str(run.id),
                    "workflow_id": str(run.workflow_id),
                    "owner_id": run.owner_id,
                    "error": str(exc.detail),
                },
            )
            return None
        executor = cls(db, run, user, graph, billing, reservation_request_id)
        if run.cancel_requested:
            await executor.cancel()
            return None
        run.status = RunStatus.running
        run.started_at = datetime.datetime.now(datetime.UTC)
        await db.commit()
        logger.info(
            "Запуск цепочки начат",
            extra=executor.log_fields(event="run.started", nodes=len(graph.nodes)),
        )
        return executor

    async def execute(self) -> None:
        context = self.build_context()
        if not context["variables"]:
            workflow = await self.db.get(Workflow, self.run.workflow_id)
            if workflow and workflow.variables:
                context["variables"] = dict(workflow.variables)
        async with httpx.AsyncClient() as client:
            registry = DefaultExecutors(
                client,
                self.pricing,
                lambda: self.billing.reservation_remaining(self.reservation_request_id),
                context.get("variables"),
            ).registry()
            try:
                blocked_edges: set[tuple[str, str]] = set()
                for node in topological_nodes(self.graph):
                    if await self.is_cancelled():
                        return
                    if not self._is_reachable(node, context, blocked_edges):
                        await self.skip_branch_node(node)
                        continue
                    await self.execute_node(node, context, registry)
                    if node.type == NodeType.IF_ELSE:
                        branch = (context.get("taken_branches") or {}).get(node.id)
                        blocked_edges.update(
                            (node.id, child_id)
                            for child_id in unselected_if_else_children(node, branch)
                        )
                self.run.output = context["nodes"]
                self.run.status = RunStatus.succeeded
                logger.info(
                    "Запуск цепочки успешно завершён",
                    extra=self.log_fields(event="run.succeeded", credits=self.run.cost),
                )
            except Exception as exc:
                self.run.status = RunStatus.failed
                self.run.error = user_visible_error(exc)
                logger.exception(
                    "Запуск цепочки завершился ошибкой",
                    extra=self.log_fields(event="run.failed", error=str(exc)[:4000], credits=self.run.cost),
                )
            self.run.finished_at = datetime.datetime.now(datetime.UTC)
            await self.db.commit()
            await release_unused_reserve(
                self.db, self.billing, self.user, self.run, self.reservation_request_id
            )

    def build_context(self) -> dict:
        run_input = dict(self.run.input)
        if self.user.chat_id and "chat_id" not in run_input:
            run_input["chat_id"] = self.user.chat_id
        return {
            "input": run_input,
            "nodes": {},
            "taken_branches": {},
            "variables": dict(self.graph.variables or {}),
        }

    def _is_reachable(
        self,
        node: WorkflowNode,
        context: dict,
        blocked_edges: set[tuple[str, str]],
    ) -> bool:
        if not node.parents:
            return True
        executed = context.get("nodes") or {}
        for parent_id in node.parents:
            if parent_id not in executed:
                continue
            if (parent_id, node.id) in blocked_edges:
                continue
            return True
        return False

    async def skip_branch_node(self, node: WorkflowNode) -> None:
        node_run = await self.get_or_create_node_run(node)
        if node_run.status == NodeRunStatus.succeeded:
            return
        node_run.status = NodeRunStatus.cancelled
        node_run.error = "Ветка IF ELSE не выбрана"
        node_run.finished_at = datetime.datetime.now(datetime.UTC)
        await self.db.commit()
        logger.info(
            "Звено пропущено: ветка не выбрана",
            extra=self.log_fields(
                event="node.skipped_branch",
                node_id=node.id,
                node_type=node_type_value(node.type),
            ),
        )

    async def is_cancelled(self) -> bool:
        await self.db.refresh(self.run)
        if not self.run.cancel_requested:
            return False
        await self.cancel()
        return True

    async def cancel(self) -> None:
        self.run.status = RunStatus.cancelled
        self.run.finished_at = datetime.datetime.now(datetime.UTC)
        await self.db.commit()
        await release_unused_reserve(
            self.db, self.billing, self.user, self.run, self.reservation_request_id
        )
        logger.info(
            "Запуск цепочки отменён",
            extra=self.log_fields(event="run.cancelled", credits=self.run.cost),
        )

    async def fail(self, error: BaseException) -> None:
        self.run.status = RunStatus.failed
        self.run.error = user_visible_error(error)
        self.run.finished_at = datetime.datetime.now(datetime.UTC)
        await self.db.commit()
        await release_unused_reserve(
            self.db, self.billing, self.user, self.run, self.reservation_request_id
        )
        logger.exception(
            "Запуск цепочки аварийно остановлен",
            extra=self.log_fields(event="run.failed", error=str(error)[:4000]),
        )

    async def execute_node(self, node: WorkflowNode, context: dict, registry: NodeRegistry) -> None:
        node_run = await self.get_or_create_node_run(node)
        if node_run.status == NodeRunStatus.succeeded:
            context["nodes"][node.id] = {"type": node_type_value(node.type), "output": node_run.output}
            logger.info(
                "Звено пропущено: уже выполнено",
                extra=self.log_fields(
                    event="node.skipped",
                    node_id=node.id,
                    node_type=node_type_value(node.type),
                ),
            )
            return
        await self.run_node_attempts(node, node_run, context, registry)

    async def get_or_create_node_run(self, node: WorkflowNode) -> NodeRun:
        node_run = await self.db.scalar(
            select(NodeRun).where(NodeRun.workflow_run_id == self.run.id, NodeRun.node_id == node.id)
        )
        if node_run:
            return node_run
        node_run = NodeRun(
            workflow_run_id=self.run.id,
            node_id=node.id,
            node_type=node.type,
            input=node.model_dump(mode="json"),
        )
        self.db.add(node_run)
        await self.db.flush()
        return node_run

    async def run_node_attempts(
        self,
        node: WorkflowNode,
        node_run: NodeRun,
        context: dict,
        registry: NodeRegistry,
    ) -> None:
        max_attempts = 1 if node.type in {
            NodeType.PROMPT, NodeType.TELEGRAM_SEND, NodeType.HTTP_REQUEST, NodeType.IF_ELSE
        } else 3
        last_error: Exception | None = None
        for attempt in range(node_run.attempt, max_attempts):
            node_run.attempt = attempt + 1
            node_run.status = NodeRunStatus.running
            node_run.started_at = datetime.datetime.now(datetime.UTC)
            await self.db.commit()
            logger.info(
                "Звено запущено",
                extra=self.log_fields(
                    event="node.started",
                    node_id=node.id,
                    node_type=node_type_value(node.type),
                    attempt=node_run.attempt,
                    label=getattr(node, "label", None),
                ),
            )
            try:
                output = jsonable_output(await registry.execute(node, context))
                await self.succeed_node(node, node_run, context, output)
                return
            except Exception as exc:
                last_error = exc
                node_run.error = user_visible_error(exc, node.type)
                node_run.status = NodeRunStatus.failed
                await self.db.commit()
                logger.exception(
                    "Звено завершилось ошибкой",
                    extra=self.log_fields(
                        event="node.failed",
                        node_id=node.id,
                        node_type=node_type_value(node.type),
                        attempt=node_run.attempt,
                        error=str(exc)[:4000],
                    ),
                )
                if attempt < max_attempts - 1:
                    await asyncio.sleep(2**attempt)
        if last_error:
            raise last_error
        raise RuntimeError(f"Узел {node.id} не выполнен")

    async def succeed_node(
        self,
        node: WorkflowNode,
        node_run: NodeRun,
        context: dict,
        output: dict | list,
    ) -> None:
        node_run.output = output
        node_run.status = NodeRunStatus.succeeded
        node_run.finished_at = datetime.datetime.now(datetime.UTC)
        context["nodes"][node.id] = {"type": node_type_value(node.type), "output": output}
        remaining = await self.billing.reservation_remaining(self.reservation_request_id)
        cost, units, details = await node_cost(self.pricing, node, output)
        if cost > 0:
            await self.billing.charge_reservation(
                self.user,
                self.reservation_request_id,
                cost,
                f"charge:{self.run.id}:{node.id}",
                units=units,
                workflow_run_id=self.run.id,
                details=details,
            )
            if cost > remaining:
                raise ValueError("Фактическая стоимость превысила остаток credits")
        extra = self.log_fields(
            event="node.succeeded",
            node_id=node.id,
            node_type=node_type_value(node.type),
            credits=cost,
            output=output_preview(output),
            **{key: details[key] for key in (
                "provider",
                "model",
                "input_cache_hit_tokens",
                "input_cache_miss_tokens",
                "output_tokens",
                "truncated",
            ) if key in details},
        )
        logger.info("Звено выполнено", extra=extra)


async def _execute_workflow(run_id: str) -> None:
    task_engine, TaskSession = task_session_factory()
    try:
        async with TaskSession() as db:
            executor = await WorkflowRunExecutor.prepare(db, run_id)
            if executor is None:
                return
            try:
                await executor.execute()
            except Exception as exc:
                # Без этого упавшая задача оставила бы run в статусе running навсегда.
                await db.rollback()
                await executor.fail(exc)
                raise
    finally:
        await task_engine.dispose()


@celery_app.task(name="execution.tasks.execute_workflow")
def execute_workflow(run_id: str) -> None:
    logger.info("Задача выполнения принята worker", extra={"event": "run.task_started", "run_id": run_id})
    asyncio.run(_execute_workflow(run_id))


async def _poll_scheduled() -> list[str]:
    now = datetime.datetime.now(datetime.UTC)
    run_ids: list[str] = []
    task_engine, TaskSession = task_session_factory()
    try:
        async with TaskSession() as db:
            workflows = list(await db.scalars(
                select(Workflow)
                .where(
                    Workflow.status == WorkflowStatus.published,
                    Workflow.next_run_at.is_not(None),
                    Workflow.next_run_at <= now,
                )
                .with_for_update(skip_locked=True)
            ))
            for workflow in workflows:
                run = WorkflowRun(
                    workflow_id=workflow.id,
                    workflow_version_id=workflow.published_version_id,
                    owner_id=workflow.owner_id,
                    input={"scheduled_at": now.isoformat()},
                )
                db.add(run)
                await db.flush()
                run_ids.append(str(run.id))
                slots = load_slots(workflow.schedule_slots) or slots_from_legacy(workflow.schedule_cron)
                slots = advance_due_slots(slots, workflow.schedule_timezone, now)
                workflow.schedule_slots = dump_slots(slots)
                workflow.next_run_at = earliest_next(slots)
                logger.info(
                    "Запланированный запуск поставлен в очередь",
                    extra={
                        "event": "run.queued",
                        "run_id": str(run.id),
                        "workflow_id": str(workflow.id),
                        "owner_id": workflow.owner_id,
                    },
                )
            await db.commit()
        return run_ids
    finally:
        await task_engine.dispose()


@celery_app.task(name="execution.tasks.poll_scheduled_workflows")
def poll_scheduled_workflows() -> None:
    for run_id in asyncio.run(_poll_scheduled()):
        execute_workflow.delay(run_id)
