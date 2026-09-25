import datetime
from enum import Enum
import json
import re
import uuid
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator, model_validator

from models.workflow import NodeRunStatus, RunStatus, WorkflowStatus
from schemas.common import SearchPeriod
from core.config import LLMProviderId


_VAR_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def normalize_workflow_variables(value: object) -> dict[str, Any]:
    if not value:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Переменные должны быть объектом")
    if len(value) > 50:
        raise ValueError("Не больше 50 переменных")
    cleaned: dict[str, Any] = {}
    for raw_key, raw_val in value.items():
        key = str(raw_key).strip()
        if not _VAR_KEY_RE.fullmatch(key):
            raise ValueError(f"Некорректное имя переменной: {raw_key}")
        cleaned[key] = raw_val
    return cleaned


class NodeVariableAssignment(BaseModel):
    key: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    value: str = Field(default="", max_length=8000)


class NodeType(str, Enum):
    WEB_SEARCH = "web_search"
    PROMPT = "prompt"
    TELEGRAM_SEND = "telegram_send"
    HTTP_REQUEST = "http_request"
    IF_ELSE = "if_else"
    WEBHOOK = "webhook"
    GOOGLE_SHEETS = "google_sheets"
    EMAIL = "email"
    DATA_TRANSFORM = "data_transform"
    SQL_QUERY = "sql_query"
    LOOP = "loop"
    DELAY = "delay"
    YANDEX_DISK = "yandex_disk"
    IMAGE_GENERATION = "image_generation"
    IMAGE = "image"
    IMAGE_RECOGNITION = "image_recognition"
    AUDIO_TRANSCRIPTION = "audio_transcription"
    SLACK = "slack"
    TRELLO = "trello"
    JIRA = "jira"
    EXCEL = "excel"
    FILE = "file"
    SPREADSHEET = "spreadsheet"
    LINKEDIN = "linkedin"

    @staticmethod
    def with_output() -> frozenset["NodeType"]:
        return frozenset({
            NodeType.WEB_SEARCH,
            NodeType.PROMPT,
            NodeType.HTTP_REQUEST,
            NodeType.IF_ELSE,
            NodeType.WEBHOOK,
            NodeType.GOOGLE_SHEETS,
            NodeType.EMAIL,
            NodeType.DATA_TRANSFORM,
            NodeType.SQL_QUERY,
            NodeType.LOOP,
            NodeType.DELAY,
            NodeType.YANDEX_DISK,
            NodeType.IMAGE_GENERATION,
            NodeType.IMAGE,
            NodeType.IMAGE_RECOGNITION,
            NodeType.AUDIO_TRANSCRIPTION,
            NodeType.SLACK,
            NodeType.TRELLO,
            NodeType.JIRA,
            NodeType.EXCEL,
            NodeType.FILE,
            NodeType.SPREADSHEET,
            NodeType.LINKEDIN,
        })

    @staticmethod
    def single_incoming() -> frozenset["NodeType"]:
        return frozenset({
            NodeType.TELEGRAM_SEND,
            NodeType.HTTP_REQUEST,
            NodeType.IF_ELSE,
            NodeType.GOOGLE_SHEETS,
            NodeType.EMAIL,
            NodeType.DATA_TRANSFORM,
            NodeType.SQL_QUERY,
            NodeType.LOOP,
            NodeType.DELAY,
            NodeType.YANDEX_DISK,
            NodeType.IMAGE_GENERATION,
            NodeType.IMAGE,
            NodeType.IMAGE_RECOGNITION,
            NodeType.AUDIO_TRANSCRIPTION,
            NodeType.SLACK,
            NodeType.TRELLO,
            NodeType.JIRA,
            NodeType.EXCEL,
            NodeType.FILE,
            NodeType.SPREADSHEET,
            NodeType.LINKEDIN,
        })


class Node(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    parents: list[str] = Field(default_factory=list)
    children: list[str] = Field(default_factory=list)
    input: str | None = None
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
    output_format: str = Field(default="", max_length=20000)
    provider: LLMProviderId | None = None
    model: str | None = None
    complexity: Literal["simple_text", "complex_text"] = "simple_text"
    max_output_tokens: int = Field(default=8000, ge=16, le=128000)
    assignments: list[NodeVariableAssignment] = Field(default_factory=list, max_length=50)
    position: dict[str, float] | None = None


class TelegramSendNode(Node):
    type: Literal[NodeType.TELEGRAM_SEND] = NodeType.TELEGRAM_SEND
    chat_id: str = Field(default="", max_length=2000)
    bot_token: str = Field(default="", max_length=200)
    message: str = Field(default="", max_length=8000)
    position: dict[str, float] | None = None

    @field_validator("chat_id", mode="before")
    @classmethod
    def coerce_chat_id(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value)

    def uses_custom_bot(self) -> bool:
        return bool((self.bot_token or "").strip())

    def chat_id_blank(self) -> bool:
        return not str(self.chat_id or "").strip()


class HttpRequestNode(Node):
    type: Literal[NodeType.HTTP_REQUEST] = NodeType.HTTP_REQUEST
    request_json: str = Field(default="", max_length=20000)
    assignments: list[NodeVariableAssignment] = Field(default_factory=list, max_length=50)
    position: dict[str, float] | None = None

    @field_validator("request_json", mode="before")
    @classmethod
    def coerce_request_json(cls, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, dict):
            return json.dumps(value, ensure_ascii=False, indent=2)
        return str(value)


class IfElseNode(Node):
    type: Literal[NodeType.IF_ELSE] = NodeType.IF_ELSE
    condition: str = Field(default="", max_length=2000)
    true_children: list[str] = Field(default_factory=list)
    false_children: list[str] = Field(default_factory=list)
    position: dict[str, float] | None = None


def _coerce_json_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return str(value)


class WebhookNode(Node):
    type: Literal[NodeType.WEBHOOK] = NodeType.WEBHOOK
    position: dict[str, float] | None = None


class GoogleSheetsNode(Node):
    type: Literal[NodeType.GOOGLE_SHEETS] = NodeType.GOOGLE_SHEETS
    operation: Literal["read", "append", "update"] = "read"
    spreadsheet_id: str = Field(default="", max_length=200)
    sheet_range: str = Field(default="Sheet1!A1:Z", max_length=500)
    access_token: str = Field(default="", max_length=8000)
    service_account_json: str = Field(default="", max_length=20000)
    api_key: str = Field(default="", max_length=500)
    values_json: str = Field(default="", max_length=20000)
    assignments: list[NodeVariableAssignment] = Field(default_factory=list, max_length=50)
    position: dict[str, float] | None = None

    @field_validator("values_json", "service_account_json", mode="before")
    @classmethod
    def coerce_sheets_json(cls, value: object) -> str:
        return _coerce_json_text(value)


class EmailNode(Node):
    type: Literal[NodeType.EMAIL] = NodeType.EMAIL
    to: str = Field(default="", max_length=2000)
    subject: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=20000)
    assignments: list[NodeVariableAssignment] = Field(default_factory=list, max_length=50)
    position: dict[str, float] | None = None


class DataTransformNode(Node):
    type: Literal[NodeType.DATA_TRANSFORM] = NodeType.DATA_TRANSFORM
    operation: Literal["select", "rename", "set", "remove", "filter", "sort", "map", "merge"] = "select"
    fields: str = Field(default="", max_length=4000)
    mapping_json: str = Field(default="", max_length=20000)
    condition: str = Field(default="", max_length=2000)
    sort_field: str = Field(default="", max_length=200)
    sort_direction: Literal["asc", "desc"] = "asc"
    path: str = Field(default="", max_length=500)
    assignments: list[NodeVariableAssignment] = Field(default_factory=list, max_length=50)
    position: dict[str, float] | None = None

    @field_validator("mapping_json", mode="before")
    @classmethod
    def coerce_mapping_json(cls, value: object) -> str:
        return _coerce_json_text(value)


class SqlQueryNode(Node):
    type: Literal[NodeType.SQL_QUERY] = NodeType.SQL_QUERY
    engine: Literal["postgresql", "mysql", "clickhouse"] = "postgresql"
    dsn: str = Field(default="", max_length=2000)
    query: str = Field(default="", max_length=20000)
    assignments: list[NodeVariableAssignment] = Field(default_factory=list, max_length=50)
    position: dict[str, float] | None = None


class LoopNode(Node):
    """Цикл внутри узла: выход — список итераций, потомки графа не повторяются."""

    type: Literal[NodeType.LOOP] = NodeType.LOOP
    mode: Literal["for_each", "times", "while"] = "for_each"
    source: str = Field(default="", max_length=2000)
    times: str = Field(default="", max_length=200)
    while_variable: str = Field(default="", max_length=80)
    while_operator: Literal[">", "<", "==", "!=", ">=", "<="] = "=="
    while_value: str = Field(default="", max_length=2000)
    position: dict[str, float] | None = None


class DelayNode(Node):
    type: Literal[NodeType.DELAY] = NodeType.DELAY
    amount: str = Field(default="1", max_length=200)
    unit: Literal["seconds", "minutes"] = "seconds"
    position: dict[str, float] | None = None


class YandexDiskNode(Node):
    type: Literal[NodeType.YANDEX_DISK] = NodeType.YANDEX_DISK
    operation: Literal["upload", "download"] = "download"
    token: str = Field(default="", max_length=2000)
    remote_path: str = Field(default="", max_length=2000)
    local_path: str = Field(default="", max_length=2000)
    content: str = Field(default="", max_length=20000)
    position: dict[str, float] | None = None


class ImageGenerationNode(Node):
    type: Literal[NodeType.IMAGE_GENERATION] = NodeType.IMAGE_GENERATION
    prompt: str = Field(default="", max_length=8000)
    position: dict[str, float] | None = None


class ImageNode(Node):
    type: Literal[NodeType.IMAGE] = NodeType.IMAGE
    source: Literal["url", "file", "upstream"] = "url"
    url: str = Field(default="", max_length=4000)
    filename: str = Field(default="", max_length=300)
    file_base64: str = Field(default="", max_length=8_000_000)
    position: dict[str, float] | None = None


class ImageRecognitionNode(Node):
    type: Literal[NodeType.IMAGE_RECOGNITION] = NodeType.IMAGE_RECOGNITION
    prompt: str = Field(default="", max_length=8000)
    position: dict[str, float] | None = None


class AudioTranscriptionNode(Node):
    type: Literal[NodeType.AUDIO_TRANSCRIPTION] = NodeType.AUDIO_TRANSCRIPTION
    source: Literal["url", "file", "upstream"] = "url"
    url: str = Field(default="", max_length=4000)
    filename: str = Field(default="", max_length=300)
    file_base64: str = Field(default="", max_length=8_000_000)
    prompt: str = Field(default="", max_length=8000)
    position: dict[str, float] | None = None


class SlackNode(Node):
    type: Literal[NodeType.SLACK] = NodeType.SLACK
    webhook_url: str = Field(default="", max_length=2000)
    bot_token: str = Field(default="", max_length=500)
    channel: str = Field(default="", max_length=200)
    message: str = Field(default="", max_length=8000)
    position: dict[str, float] | None = None


class TrelloNode(Node):
    type: Literal[NodeType.TRELLO] = NodeType.TRELLO
    operation: Literal["create_card", "list_cards", "move_card", "add_comment"] = "create_card"
    api_key: str = Field(default="", max_length=500)
    token: str = Field(default="", max_length=500)
    list_id: str = Field(default="", max_length=200)
    card_id: str = Field(default="", max_length=200)
    name: str = Field(default="", max_length=2000)
    description: str = Field(default="", max_length=16000)
    assignments: list[NodeVariableAssignment] = Field(default_factory=list, max_length=50)
    position: dict[str, float] | None = None


class JiraNode(Node):
    type: Literal[NodeType.JIRA] = NodeType.JIRA
    operation: Literal["create_issue", "search", "add_comment"] = "create_issue"
    base_url: str = Field(default="", max_length=500)
    email: str = Field(default="", max_length=320)
    api_token: str = Field(default="", max_length=500)
    project_key: str = Field(default="", max_length=50)
    issue_type: str = Field(default="Task", max_length=100)
    summary: str = Field(default="", max_length=1000)
    description: str = Field(default="", max_length=16000)
    jql: str = Field(default="", max_length=4000)
    issue_key: str = Field(default="", max_length=100)
    comment: str = Field(default="", max_length=16000)
    assignments: list[NodeVariableAssignment] = Field(default_factory=list, max_length=50)
    position: dict[str, float] | None = None


class ExcelNode(Node):
    """Книга Excel в OneDrive / Microsoft 365 через Microsoft Graph."""

    type: Literal[NodeType.EXCEL] = NodeType.EXCEL
    operation: Literal["read", "append", "update"] = "read"
    access_token: str = Field(default="", max_length=8000)
    file_path: str = Field(default="", max_length=1000)
    worksheet: str = Field(default="Sheet1", max_length=200)
    cell_range: str = Field(default="", max_length=200)
    table: str = Field(default="", max_length=200)
    values_json: str = Field(default="", max_length=20000)
    assignments: list[NodeVariableAssignment] = Field(default_factory=list, max_length=50)
    position: dict[str, float] | None = None

    @field_validator("values_json", mode="before")
    @classmethod
    def coerce_excel_json(cls, value: object) -> str:
        return _coerce_json_text(value)


class FileNode(Node):
    """Локальный файл, загруженный в цепочку."""

    type: Literal[NodeType.FILE] = NodeType.FILE
    filename: str = Field(default="", max_length=300)
    file_base64: str = Field(default="", max_length=14_000_000)
    position: dict[str, float] | None = None


class SpreadsheetNode(Node):
    """Таблица CSV/XLSX: читает файл предыдущего узла или собирает файл из данных."""

    type: Literal[NodeType.SPREADSHEET] = NodeType.SPREADSHEET
    operation: Literal["read", "write"] = "read"
    file_format: Literal["auto", "csv", "xlsx"] = "auto"
    sheet: str = Field(default="", max_length=200)
    header_row: bool = True
    delimiter: str = Field(default="", max_length=4)
    path: str = Field(default="", max_length=500)
    filename: str = Field(default="", max_length=300)
    assignments: list[NodeVariableAssignment] = Field(default_factory=list, max_length=50)
    position: dict[str, float] | None = None


class LinkedInNode(Node):
    type: Literal[NodeType.LINKEDIN] = NodeType.LINKEDIN
    access_token: str = Field(default="", max_length=4000)
    author: str = Field(default="", max_length=200)
    text: str = Field(default="", max_length=3000)
    visibility: Literal["PUBLIC", "CONNECTIONS"] = "PUBLIC"
    position: dict[str, float] | None = None


WorkflowNode = Annotated[
    WebSearchNode
    | PromptNode
    | TelegramSendNode
    | HttpRequestNode
    | IfElseNode
    | WebhookNode
    | GoogleSheetsNode
    | EmailNode
    | DataTransformNode
    | SqlQueryNode
    | LoopNode
    | DelayNode
    | YandexDiskNode
    | ImageGenerationNode
    | ImageNode
    | ImageRecognitionNode
    | AudioTranscriptionNode
    | SlackNode
    | TrelloNode
    | JiraNode
    | ExcelNode
    | FileNode
    | SpreadsheetNode
    | LinkedInNode,
    Field(discriminator="type"),
]


class WorkflowGraph(BaseModel):
    nodes: list[WorkflowNode] = Field(default_factory=list, max_length=100)
    variables: dict[str, Any] = Field(default_factory=dict)

    @field_validator("variables", mode="before")
    @classmethod
    def clean_graph_variables(cls, value: object) -> dict[str, Any]:
        return normalize_workflow_variables(value)

    @model_validator(mode="before")
    @classmethod
    def take_nodes(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        nodes = [dict(node) if isinstance(node, dict) else node for node in (data.get("nodes") or [])]
        for node in nodes:
            if isinstance(node, dict) and node.get("type") == "gmail":
                node["type"] = "email"
                if not node.get("body") and node.get("message"):
                    node["body"] = node.get("message")
        for edge in data.get("edges") or []:
            if not isinstance(edge, dict):
                continue
            source, target = edge.get("source"), edge.get("target")
            handle = str(edge.get("sourceHandle") or "")
            branch = (
                "true" if handle == "true" or handle.endswith("-true")
                else "false" if handle == "false" or handle.endswith("-false")
                else None
            )
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                if source and node.get("id") == source:
                    children = list(node.get("children") or [])
                    if target and target not in children:
                        children.append(target)
                    node["children"] = children
                    if branch and target:
                        key = f"{branch}_children"
                        branched = list(node.get(key) or [])
                        if target not in branched:
                            branched.append(target)
                        node[key] = branched
                if target and node.get("id") == target:
                    parents = list(node.get("parents") or [])
                    if source and source not in parents:
                        parents.append(source)
                    node["parents"] = parents
        payload: dict = {"nodes": nodes}
        if "variables" in data:
            payload["variables"] = data.get("variables") or {}
        return payload

    @model_validator(mode="after")
    def sync_adjacency(self) -> Self:
        links: set[tuple[str, str]] = set()
        true_saved: dict[str, list[str]] = {}
        false_saved: dict[str, list[str]] = {}
        for node in self.nodes:
            links.update((node.id, child_id) for child_id in node.children)
            links.update((parent_id, node.id) for parent_id in node.parents)
            if isinstance(node, IfElseNode):
                links.update((node.id, child_id) for child_id in node.true_children)
                links.update((node.id, child_id) for child_id in node.false_children)
                true_saved[node.id] = list(node.true_children)
                false_saved[node.id] = list(node.false_children)
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
            if isinstance(node, IfElseNode):
                known = set(node.children)
                node.true_children = [child_id for child_id in true_saved.get(node.id, []) if child_id in known]
                node.false_children = [child_id for child_id in false_saved.get(node.id, []) if child_id in known]
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


class WeeklyScheduleSlot(BaseModel):
    id: str = Field(default="", max_length=40)
    kind: Literal["weekly"] = "weekly"
    time: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    weekdays: list[Annotated[int, Field(ge=1, le=7)]] = Field(min_length=1)
    next_at: datetime.datetime | None = None

    @model_validator(mode="after")
    def normalize_weekdays(self) -> Self:
        self.weekdays = sorted(set(self.weekdays))
        return self


class IntervalScheduleSlot(BaseModel):
    id: str = Field(default="", max_length=40)
    kind: Literal["interval"] = "interval"
    every: int = Field(ge=1, le=1440)
    unit: Literal["minutes", "hours", "days"]
    next_at: datetime.datetime | None = None


ScheduleSlot = Annotated[WeeklyScheduleSlot | IntervalScheduleSlot, Field(discriminator="kind")]


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    graph: WorkflowGraph = Field(default_factory=lambda: WorkflowGraph(nodes=[]))
    schedule: WorkflowSchedule | None = None
    schedule_slots: list[ScheduleSlot] | None = None
    schedule_enabled: bool | None = None
    schedule_cron: str | None = None
    schedule_timezone: str = "UTC"
    variables: dict[str, Any] | None = None

    @field_validator("variables")
    @classmethod
    def clean_create_variables(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        return normalize_workflow_variables(value)


class WorkflowUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=160)
    description: str | None = None
    variables: dict[str, Any] | None = None
    graph: WorkflowGraph | None = None
    schedule: WorkflowSchedule | None = None
    schedule_slots: list[ScheduleSlot] | None = None
    schedule_enabled: bool | None = None
    schedule_cron: str | None = None
    schedule_timezone: str | None = None
    rotate_webhook_token: bool | None = None

    @field_validator("variables")
    @classmethod
    def clean_update_variables(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        return normalize_workflow_variables(value)


class WorkflowResponse(BaseModel):
    id: uuid.UUID
    owner_id: int
    name: str
    description: str | None
    status: WorkflowStatus
    draft_graph: dict
    variables: dict[str, Any] = Field(default_factory=dict)
    published_version_id: uuid.UUID | None
    schedule_cron: str | None
    schedule_slots: list[dict] = Field(default_factory=list)
    schedule_timezone: str
    next_run_at: datetime.datetime | None
    estimated_run_cost: Decimal = Decimal("0")
    webhook_token: str | None = None
    solo_run_blocked_node_types: list[str] = Field(default_factory=list)
    created_at: datetime.datetime
    updated_at: datetime.datetime
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def fill_solo_run_policy(self) -> Self:
        from core.config import settings

        self.solo_run_blocked_node_types = sorted(settings.solo_run_blocked_types())
        return self

    @field_validator("schedule_slots", mode="before")
    @classmethod
    def default_slots(cls, value: object) -> object:
        return value or []

    @field_serializer("draft_graph")
    def dump_draft_graph(self, value: dict | None) -> dict:
        return WorkflowGraph.model_validate(value or {"nodes": []}).model_dump(mode="json")


class RunCreate(BaseModel):
    input: dict = Field(default_factory=dict)


class SoloNodeRunCreate(BaseModel):
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
