"""Файлы пользователя лежат в JSON цепочек: удаление после окончания подписки и подрезка под лимиты тарифа."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes

from models.workflow import Workflow, WorkflowVersion
from services.stored_images import STORED_FILE_NODE_TYPES, strip_stored_images, uploaded_images


@dataclass
class _StoredFile:
    workflow: Workflow
    node_id: str
    size: int


async def _load(db: AsyncSession, user_id: int) -> tuple[list[Workflow], dict]:
    workflows = list(await db.scalars(
        select(Workflow).where(Workflow.owner_id == user_id).order_by(Workflow.updated_at)
    ))
    versions: dict = defaultdict(list)
    if workflows:
        for version in await db.scalars(
            select(WorkflowVersion).where(WorkflowVersion.workflow_id.in_([item.id for item in workflows]))
        ):
            versions[version.workflow_id].append(version)
    return workflows, versions


def _files(workflows: list[Workflow], versions: dict) -> list[_StoredFile]:
    """Тот же подсчёт, что и в квоте: файлы черновика плюс файлы опубликованного снимка, которых нет в черновике."""
    found: list[_StoredFile] = []
    for workflow in workflows:
        draft = uploaded_images(workflow.draft_graph or {})
        seen = {node_id for node_id, _ in draft}
        found.extend(_StoredFile(workflow, node_id, size) for node_id, size in draft)
        published = next((item for item in versions[workflow.id] if item.id == workflow.published_version_id), None)
        if published is not None:
            found.extend(
                _StoredFile(workflow, node_id, size)
                for node_id, size in uploaded_images(published.graph_snapshot or {})
                if node_id not in seen
            )
    return found


def _blank_node(graph: object, node_id: str) -> bool:
    nodes = graph.get("nodes") if isinstance(graph, dict) else None
    changed = False
    for node in nodes if isinstance(nodes, list) else []:
        if (
            isinstance(node, dict)
            and node.get("id") == node_id
            and node.get("type") in STORED_FILE_NODE_TYPES
            and node.get("file_base64")
        ):
            node["file_base64"] = ""
            changed = True
    return changed


def _delete(item: _StoredFile, versions: dict) -> None:
    workflow = item.workflow
    if _blank_node(workflow.draft_graph, item.node_id):
        attributes.flag_modified(workflow, "draft_graph")
    for version in versions[workflow.id]:
        if _blank_node(version.graph_snapshot, item.node_id):
            attributes.flag_modified(version, "graph_snapshot")


async def purge_user_files(db: AsyncSession, user_id: int) -> int:
    """Стирает все загруженные файлы пользователя из черновиков и снимков. Возвращает число цепочек с файлами."""
    workflows, versions = await _load(db, user_id)
    touched = 0
    for workflow in workflows:
        changed = False
        if isinstance(workflow.draft_graph, dict) and strip_stored_images(workflow.draft_graph):
            attributes.flag_modified(workflow, "draft_graph")
            changed = True
        for version in versions[workflow.id]:
            if isinstance(version.graph_snapshot, dict) and strip_stored_images(version.graph_snapshot):
                attributes.flag_modified(version, "graph_snapshot")
                changed = True
        touched += int(changed)
    return touched


async def trim_user_files(db: AsyncSession, user_id: int, max_files: int, max_bytes: int) -> int:
    """Удаляет файлы, пока они не уложатся в лимиты. Сначала из давно не менявшихся цепочек. Возвращает число удалённых."""
    workflows, versions = await _load(db, user_id)
    files = _files(workflows, versions)
    count = len(files)
    total = sum(item.size for item in files)
    removed = 0
    for item in files:
        if count <= max_files and total <= max_bytes:
            break
        _delete(item, versions)
        count -= 1
        total -= item.size
        removed += 1
    return removed
