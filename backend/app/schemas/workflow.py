import datetime
from enum import Enum
import uuid
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from models.workflow import NodeRunStatus, RunStatus, WorkflowStatus
from schemas.common import SearchPeriod
from core.config import LLMProviderId


class NodeType(str, Enum):
    WEB_SEARCH = "web_search"
    PROMPT = "prompt"
    TELEGRAM_SEND = "telegram_send"

    @staticmethod
    def with_output() -> frozenset["NodeType"]:
        return frozenset({NodeType.WEB_SEARCH, NodeType.PROMPT})


class Node(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    parents: list[str] = Field(default_factory=list)
    children: list[str] = Field(default_factory=list)
    type: NodeType = Field()
    label: str | None = None


class WebSearchNode(Node):
    type: Literal[NodeType.WEB_SEARCH] = NodeType.WEB_SEARCH
    query: str = Field(default="", max_length=8000)
    period: SearchPeriod | None = None
    position: dict[str, float] | None = None


class PromptNode(Node):
    type: Literal[NodeType.PROMPT] = NodeType.PROMPT
    prompt: str = Field(default="", max_length=20000)
    instructions: str = Field(default="", max_length=500)
    provider: LLMProviderId | None = None
    model: str | None = None
    complexity: Literal["simple_text", "complex_text"] = "simple_text"
    position: dict[str, float] | None = None


class TelegramSendNode(Node):
    type: Literal[NodeType.TELEGRAM_SEND] = NodeType.TELEGRAM_SEND
    chat_id: int | None = None
    position: dict[str, float] | None = None


WorkflowNode = Annotated[
    WebSearchNode | PromptNode | TelegramSendNode,
    Field(discriminator="type"),
]


class WorkflowGraph(BaseModel):
    nodes: list[WorkflowNode] = Field(default_factory=list, max_length=100)

    @model_validator(mode="before")
    @classmethod
    def take_nodes(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        nodes = [dict(node) if isinstance(node, dict) else node for node in (data.get("nodes") or [])]
        for edge in data.get("edges") or []:
            if not isinstance(edge, dict):
                continue
            source, target = edge.get("source"), edge.get("target")
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                if source and node.get("id") == source:
                    children = list(node.get("children") or [])
                    if target and target not in children:
                        children.append(target)
                    node["children"] = children
                if target and node.get("id") == target:
                    parents = list(node.get("parents") or [])
                    if source and source not in parents:
                        parents.append(source)
                    node["parents"] = parents
        return {"nodes": nodes}

    @model_validator(mode="after")
    def sync_adjacency(self) -> Self:
        links: set[tuple[str, str]] = set()
        for node in self.nodes:
            links.update((node.id, child_id) for child_id in node.children)
            links.update((parent_id, node.id) for parent_id in node.parents)
        children: dict[str, list[str]] = {node.id: [] for node in self.nodes}
        parents: dict[str, list[str]] = {node.id: [] for node in self.nodes}
        for source, target in sorted(links):
            if source in children:
                children[source].append(target)
            if target in parents:
                parents[target].append(source)
        for node in self.nodes:
            node.children = children[node.id]
            node.parents = parents[node.id]
        return self


class WorkflowSchedule(BaseModel):
    time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    weekdays: list[Annotated[int, Field(ge=1, le=7)]] = Field(
        default_factory=lambda: [1, 2, 3, 4, 5, 6, 7],
        min_length=1,
    )

    @model_validator(mode="after")
    def normalize_weekdays(self) -> Self:
        self.weekdays = sorted(set(self.weekdays))
        return self


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    graph: WorkflowGraph = Field(default_factory=lambda: WorkflowGraph(nodes=[]))
    schedule: WorkflowSchedule | None = None
    schedule_cron: str | None = None
    schedule_timezone: str = "UTC"


class WorkflowUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=160)
    description: str | None = None
    graph: WorkflowGraph | None = None
    schedule: WorkflowSchedule | None = None
    schedule_cron: str | None = None
    schedule_timezone: str | None = None


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    owner_id: int
    name: str
    description: str | None
    status: WorkflowStatus
    draft_graph: dict
    published_version_id: uuid.UUID | None
    schedule_cron: str | None
    schedule_timezone: str
    next_run_at: datetime.datetime | None
    estimated_run_cost: Decimal = Decimal("0")
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("draft_graph")
    def dump_draft_graph(self, value: dict | None) -> dict:
        return WorkflowGraph.model_validate(value or {"nodes": []}).model_dump(mode="json")


class RunCreate(BaseModel):
    input: dict = Field(default_factory=dict)


class RunResponse(BaseModel):
    id: uuid.UUID
    workflow_id: uuid.UUID
    workflow_version_id: uuid.UUID
    workflow_name: str | None = None
    owner_id: int
    status: RunStatus
    input: dict
    output: dict | None
    error: str | None
    cost: Decimal = Decimal("0")
    cancel_requested: bool
    started_at: datetime.datetime | None
    finished_at: datetime.datetime | None
    created_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)


class NodeRunResponse(BaseModel):
    id: uuid.UUID
    workflow_run_id: uuid.UUID
    node_id: str
    node_type: str
    status: NodeRunStatus
    attempt: int
    input: dict
    output: dict | list | None
    error: str | None
    started_at: datetime.datetime | None
    finished_at: datetime.datetime | None
    model_config = ConfigDict(from_attributes=True)


class RunStepResponse(BaseModel):
    """Шаг запуска: все узлы опубликованного графа, включая ещё не начатые."""

    node_id: str
    node_type: str
    label: str | None = None
    status: NodeRunStatus = NodeRunStatus.pending
    attempt: int = 0
    output: dict | list | None = None
    error: str | None = None
    started_at: datetime.datetime | None = None
    finished_at: datetime.datetime | None = None
