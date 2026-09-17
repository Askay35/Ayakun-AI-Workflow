import json

import pytest

from core.config import settings
from core.user_errors import ERROR_GOOGLE_SHEETS
from helper import apply_variable_assignments
from schemas.workflow import (
    DataTransformNode,
    EmailNode,
    GoogleSheetsNode,
    NodeType,
    PromptNode,
    SqlQueryNode,
    WebhookNode,
    WorkflowGraph,
)
from services.execution.actions.data_transform import DataTransformAction
from services.execution.actions.email import EmailAction
from services.execution.actions.google_sheets import GoogleSheetsAction
from services.execution.actions.sql_query import SqlQueryAction, _is_app_database
from services.execution.actions.webhook import WebhookAction
from services.execution.executors import DefaultExecutors
from services.workflow import validate_graph, validate_solo_node
from execution.tasks import snapshot_node_input


def test_workflow_graph_accepts_new_node_types() -> None:
    graph = WorkflowGraph(nodes=[
        WebhookNode(id="hook", children=["transform"]),
        DataTransformNode(id="transform", operation="select", fields="id,name", parents=["hook"], children=["sql"]),
        SqlQueryNode(id="sql", dsn="postgresql://u:p@localhost:5432/app", query="SELECT 1", parents=["transform"]),
    ])
    assert [node.type for node in graph.nodes] == [NodeType.WEBHOOK, NodeType.DATA_TRANSFORM, NodeType.SQL_QUERY]
    assert validate_graph(graph) == []


def test_webhook_must_be_unique_start() -> None:
    two = WorkflowGraph(nodes=[WebhookNode(id="a"), WebhookNode(id="b")])
    assert any("только один вебхук" in item for item in validate_graph(two))
    nested = WorkflowGraph(nodes=[
        PromptNode(id="prompt", prompt="ok", children=["hook"]),
        WebhookNode(id="hook", parents=["prompt"]),
    ])
    assert any("стартовым" in item for item in validate_graph(nested))


def test_new_nodes_single_incoming() -> None:
    graph = WorkflowGraph(nodes=[
        PromptNode(id="a", prompt="A", children=["sheets"]),
        PromptNode(id="b", prompt="B", children=["sheets"]),
        GoogleSheetsNode(id="sheets", spreadsheet_id="abc", access_token="token", parents=["a", "b"]),
    ])
    errors = validate_graph(graph, strict=True)
    assert any("только одну входящую связь" in item for item in errors)


@pytest.mark.asyncio
async def test_webhook_action_wraps_raw_input() -> None:
    output = await WebhookAction().execute(
        WebhookNode(id="hook"),
        {"input": {"order_id": 17, "_solo": True}},
    )
    assert output["body"] == {"order_id": 17}
    assert output["method"] == "POST"


@pytest.mark.asyncio
async def test_webhook_action_keeps_envelope() -> None:
    output = await WebhookAction().execute(
        WebhookNode(id="hook"),
        {"input": {"method": "PUT", "headers": {"X-Test": "1"}, "query": {"a": "b"}, "body": {"ok": True}}},
    )
    assert output["method"] == "PUT"
    assert output["body"] == {"ok": True}
    assert output["query"] == {"a": "b"}


@pytest.mark.asyncio
async def test_transform_select_rename_set_remove() -> None:
    action = DataTransformAction()
    parent = {"id": 1, "name": "Ada", "secret": "x", "role": "admin"}
    context = {"nodes": {"http": {"type": "http_request", "output": parent}}, "variables": {}}
    selected = await action.execute(
        DataTransformNode(id="t", operation="select", fields="id,name", parents=["http"]),
        context,
    )
    assert selected == {"id": 1, "name": "Ada"}
    renamed = await action.execute(
        DataTransformNode(id="t", operation="rename", mapping_json='{"name": "full_name"}', parents=["http"]),
        context,
    )
    assert renamed["full_name"] == "Ada"
    assert "name" not in renamed
    updated = await action.execute(
        DataTransformNode(id="t", operation="set", mapping_json="status=active\nrole={{$role}}", parents=["http"]),
        context,
    )
    assert updated["status"] == "active"
    assert updated["role"] == "admin"
    cleaned = await action.execute(
        DataTransformNode(id="t", operation="remove", fields="secret", parents=["http"]),
        context,
    )
    assert "secret" not in cleaned
    assert cleaned["name"] == "Ada"


@pytest.mark.asyncio
async def test_transform_filter_sort_map_on_array() -> None:
    action = DataTransformAction()
    rows = [{"name": "b", "score": 1}, {"name": "a", "score": 3}, {"name": "c", "score": 2}]
    context = {"nodes": {"src": {"type": "http_request", "output": {"items": rows}}}, "variables": {}}
    filtered = await action.execute(
        DataTransformNode(id="t", operation="filter", condition="{{$score}} >= 2", path="items", parents=["src"]),
        context,
    )
    assert [item["name"] for item in filtered] == ["a", "c"]
    sorted_rows = await action.execute(
        DataTransformNode(id="t", operation="sort", sort_field="name", sort_direction="asc", path="items", parents=["src"]),
        context,
    )
    assert [item["name"] for item in sorted_rows] == ["a", "b", "c"]
    mapped = await action.execute(
        DataTransformNode(
            id="t",
            operation="map",
            mapping_json='{"title": "{{$name}}", "points": "{{$score}}"}',
            path="items",
            parents=["src"],
        ),
        context,
    )
    assert mapped[0]["title"] == "b"
    assert mapped[0]["points"] == 1


@pytest.mark.asyncio
async def test_transform_assigns_variable() -> None:
    from schemas.workflow import NodeVariableAssignment

    action = DataTransformAction()
    context = {
        "nodes": {"src": {"type": "webhook", "output": {"body": {"count": 4}}}},
        "variables": {},
    }
    await action.execute(
        DataTransformNode(
            id="t",
            operation="select",
            fields="count",
            path="body",
            assignments=[NodeVariableAssignment(key="n", value="{{$count}}")],
            parents=["src"],
        ),
        context,
    )
    assert context["variables"]["n"] == 4


class FakeSheetsResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status
        self.is_error = status >= 400
        self.content = json.dumps(payload).encode()

    def json(self) -> dict:
        return self._payload


class FakeSheetsClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    async def get(self, url, **kwargs):
        self.calls.append({"method": "GET", "url": url, **kwargs})
        return FakeSheetsResponse(self.payload)

    async def post(self, url, **kwargs):
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return FakeSheetsResponse(self.payload)

    async def put(self, url, **kwargs):
        self.calls.append({"method": "PUT", "url": url, **kwargs})
        return FakeSheetsResponse(self.payload)


@pytest.mark.asyncio
async def test_google_sheets_read_builds_row_objects() -> None:
    client = FakeSheetsClient({
        "range": "Sheet1!A1:B3",
        "values": [["name", "score"], ["Ada", "3"], ["Lin", "1"]],
    })
    action = GoogleSheetsAction(client)
    result = await action.execute(
        GoogleSheetsNode(id="sheets", spreadsheet_id="spread1", sheet_range="Sheet1!A1:B", access_token="tok"),
        {"nodes": {}, "variables": {}},
    )
    assert result["rows"] == [{"name": "Ada", "score": "3"}, {"name": "Lin", "score": "1"}]
    assert result["row_count"] == 2
    assert "spread1" in client.calls[0]["url"]
    assert client.calls[0]["headers"]["Authorization"] == "Bearer tok"


@pytest.mark.asyncio
async def test_google_sheets_append_sends_values() -> None:
    client = FakeSheetsClient({"updates": {"updatedRows": 1, "updatedCells": 2}, "updatedRange": "Sheet1!A2:B2"})
    action = GoogleSheetsAction(client)
    result = await action.execute(
        GoogleSheetsNode(
            id="sheets",
            operation="append",
            spreadsheet_id="spread1",
            sheet_range="Sheet1!A1",
            access_token="tok",
            values_json='[["Ada", 3]]',
        ),
        {"nodes": {}, "variables": {}},
    )
    assert client.calls[0]["method"] == "POST"
    assert client.calls[0]["json"] == {"values": [["Ada", 3]]}
    assert result["updated_rows"] == 1


@pytest.mark.asyncio
async def test_google_sheets_network_error_is_generic() -> None:
    import httpx

    class ErrorClient:
        async def get(self, *args, **kwargs):
            raise httpx.ConnectError("dns", request=httpx.Request("GET", "https://sheets.googleapis.com"))

    action = GoogleSheetsAction(ErrorClient())
    with pytest.raises(ValueError, match=ERROR_GOOGLE_SHEETS):
        await action.execute(
            GoogleSheetsNode(id="sheets", spreadsheet_id="id", access_token="tok"),
            {"nodes": {}, "variables": {}},
        )


@pytest.mark.asyncio
async def test_email_send_renders_templates() -> None:
    class FakeMail:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str, str]] = []

        async def send(self, recipient: str, subject: str, text: str) -> None:
            self.calls.append((recipient, subject, text))

    mail = FakeMail()
    result = await EmailAction(mail).execute(
        EmailNode(
            id="mail",
            to="{{$email}}",
            subject="Hi {{name}}",
            body="{% for item in $items %}{{item.title}}\n{% endfor %}",
            parents=["src"],
        ),
        {
            "nodes": {
                "src": {
                    "type": "webhook",
                    "output": {
                        "email": "ada@example.com",
                        "items": [{"title": "A"}, {"title": "B"}],
                    },
                }
            },
            "variables": {"name": "Ada"},
        },
    )
    assert result["sent"] is True
    assert result["to"] == ["ada@example.com"]
    assert result["subject"] == "Hi Ada"
    assert mail.calls == [("ada@example.com", "Hi Ada", "A\nB\n")]


@pytest.mark.asyncio
async def test_email_send_requires_recipient() -> None:
    class FakeMail:
        async def send(self, recipient: str, subject: str, text: str) -> None:
            raise AssertionError("should not send")

    with pytest.raises(ValueError, match="Укажите получателя письма"):
        await EmailAction(FakeMail()).execute(
            EmailNode(id="mail", to=""),
            {"nodes": {}, "variables": {}},
        )


@pytest.mark.asyncio
async def test_email_send_when_smtp_missing() -> None:
    from fastapi import HTTPException

    class BrokenMail:
        async def send(self, recipient: str, subject: str, text: str) -> None:
            raise HTTPException(503, "Email provider не настроен")

    with pytest.raises(ValueError, match="Почта не настроена"):
        await EmailAction(BrokenMail()).execute(
            EmailNode(id="mail", to="ada@example.com", subject="Hi", body="Hello"),
            {"nodes": {}, "variables": {}},
        )


@pytest.mark.asyncio
async def test_sql_query_returns_json_rows(monkeypatch) -> None:
    class FakeRecord(dict):
        pass

    class FakeConn:
        async def execute(self, query):
            return "SET"

        async def fetch(self, query):
            assert "FROM users" in query
            return [FakeRecord(id=1, name="Ada")]

        async def close(self):
            return None

    async def fake_connect(**kwargs):
        return FakeConn()

    monkeypatch.setattr("services.execution.actions.sql_query.asyncpg.connect", fake_connect)
    result = await SqlQueryAction().execute(
        SqlQueryNode(id="sql", dsn="postgresql://u:p@db.example:5432/app", query="SELECT id, name FROM users"),
        {"nodes": {}, "variables": {}},
    )
    assert result == {"engine": "postgresql", "rows": [{"id": 1, "name": "Ada"}], "row_count": 1}


@pytest.mark.asyncio
async def test_sql_query_blocks_app_database() -> None:
    assert _is_app_database(settings.db_url) is True
    with pytest.raises(ValueError, match="служебной базе"):
        await SqlQueryAction().execute(
            SqlQueryNode(id="sql", dsn=settings.db_url, query="SELECT 1"),
            {"nodes": {}, "variables": {}},
        )


def test_sql_strict_validation_requires_dsn_and_query() -> None:
    graph = WorkflowGraph(nodes=[SqlQueryNode(id="sql")])
    errors = validate_graph(graph, strict=True)
    assert any("строку подключения" in item for item in errors)
    assert any("SQL-запрос" in item for item in errors)


def test_transform_strict_validation() -> None:
    graph = WorkflowGraph(nodes=[DataTransformNode(id="t", operation="filter")])
    errors = validate_graph(graph, strict=True)
    assert any("условие Filter" in item for item in errors)


def test_solo_sheets_requires_spreadsheet() -> None:
    errors = validate_solo_node(GoogleSheetsNode(id="sheets"))
    assert any("идентификатор таблицы" in item for item in errors)


def test_snapshot_redacts_secrets() -> None:
    node = SqlQueryNode(id="sql", dsn="postgresql://u:secret@db/app", query="SELECT 1")
    dumped = snapshot_node_input(node)
    assert dumped["dsn"] == "***"
    assert dumped["query"] == "SELECT 1"


def test_new_types_have_output() -> None:
    assert NodeType.WEBHOOK in NodeType.with_output()
    assert NodeType.EMAIL in NodeType.with_output()
    assert NodeType.SQL_QUERY in NodeType.with_output()
    assert NodeType.DATA_TRANSFORM in NodeType.with_output()


def test_default_executors_register_new_types() -> None:
    executors = object.__new__(DefaultExecutors)
    registry = DefaultExecutors.registry(executors)
    for node_type in (
        NodeType.WEBHOOK,
        NodeType.GOOGLE_SHEETS,
        NodeType.EMAIL,
        NodeType.DATA_TRANSFORM,
        NodeType.SQL_QUERY,
    ):
        assert node_type in registry._executors


def test_gmail_graph_migrates_to_email() -> None:
    graph = WorkflowGraph.model_validate({
        "nodes": [{"id": "mail", "type": "gmail", "to": "ada@example.com", "subject": "Hi", "body": "Hello"}],
    })
    assert graph.nodes[0].type == NodeType.EMAIL
    assert graph.nodes[0].to == "ada@example.com"


def test_email_validation_requires_recipient() -> None:
    errors = validate_solo_node(EmailNode(id="mail"))
    assert any("получателя письма" in item for item in errors)
    connected = validate_solo_node(EmailNode(id="mail", to="ada@example.com"))
    assert connected == []


@pytest.mark.asyncio
async def test_sql_query_mysql(monkeypatch) -> None:
    async def fake_mysql(dsn, query):
        assert dsn.startswith("mysql://")
        assert "FROM users" in query
        return {"engine": "mysql", "rows": [{"id": 2}], "row_count": 1}

    monkeypatch.setattr("services.execution.actions.sql_query._mysql", fake_mysql)
    result = await SqlQueryAction().execute(
        SqlQueryNode(id="sql", engine="mysql", dsn="mysql://u:p@db.example:3306/app", query="SELECT id FROM users"),
        {"nodes": {}, "variables": {}},
    )
    assert result == {"engine": "mysql", "rows": [{"id": 2}], "row_count": 1}


@pytest.mark.asyncio
async def test_sql_query_clickhouse(monkeypatch) -> None:
    def fake_clickhouse(dsn, query):
        assert dsn.startswith("clickhouse://")
        assert query.startswith("SELECT")
        return {"engine": "clickhouse", "rows": [{"n": 1}], "row_count": 1}

    monkeypatch.setattr("services.execution.actions.sql_query._clickhouse", fake_clickhouse)
    result = await SqlQueryAction().execute(
        SqlQueryNode(id="sql", engine="clickhouse", dsn="clickhouse://u:p@db.example:8123/app", query="SELECT 1 AS n"),
        {"nodes": {}, "variables": {}},
    )
    assert result == {"engine": "clickhouse", "rows": [{"n": 1}], "row_count": 1}


def test_sql_rejects_unknown_scheme() -> None:
    from services.execution.actions.sql_query import _engine_from_dsn

    with pytest.raises(ValueError, match="Поддерживаются PostgreSQL, MySQL и ClickHouse"):
        _engine_from_dsn("sqlite:///tmp.db", "postgresql")


def test_encrypt_secret_roundtrip() -> None:
    import helper
    token = helper.encrypt_secret("refresh-token")
    assert token != "refresh-token"
    assert helper.decrypt_secret(token) == "refresh-token"


def test_apply_assignments_still_works_on_transform_output() -> None:
    context: dict = {"variables": {}}
    apply_variable_assignments([{"key": "n", "value": "{{$count}}"}], {"count": 9}, context)
    assert context["variables"]["n"] == 9
