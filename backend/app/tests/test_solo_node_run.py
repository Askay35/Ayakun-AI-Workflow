from schemas.workflow import HttpRequestNode, IfElseNode, PromptNode, TelegramSendNode, WebSearchNode
from services.workflow import solo_graph_for_node, validate_solo_node
from core.config import settings


def test_solo_graph_clears_parents_and_children() -> None:
    node = PromptNode(
        id="prompt",
        prompt="hello",
        parents=["search"],
        children=["http"],
    )
    graph = solo_graph_for_node(node)
    assert len(graph.nodes) == 1
    solo = graph.nodes[0]
    assert solo.id == "prompt"
    assert solo.parents == []
    assert solo.children == []


def test_validate_solo_node_blocks_if_else_by_default(monkeypatch) -> None:
    monkeypatch.setattr(settings, "solo_run_blocked_node_types", "if_else")
    node = IfElseNode(id="iff", condition='{{$x}} == 1', parents=["a"])
    errors = validate_solo_node(node)
    assert any("нельзя запускать отдельно" in item for item in errors)


def test_validate_solo_node_allows_prompt() -> None:
    node = PromptNode(id="prompt", prompt="Сделай краткий вывод")
    assert validate_solo_node(node) == []


def test_validate_solo_node_requires_http_json() -> None:
    node = HttpRequestNode(id="http", request_json="")
    errors = validate_solo_node(node)
    assert any("данные запроса" in item for item in errors)


def test_validate_solo_node_requires_web_search_query() -> None:
    node = WebSearchNode(id="search", query="  ")
    errors = validate_solo_node(node)
    assert any("поисковый запрос" in item for item in errors)


def test_blocked_types_from_config_csv(monkeypatch) -> None:
    monkeypatch.setattr(settings, "solo_run_blocked_node_types", "if_else, telegram_send")
    blocked = settings.solo_run_blocked_types()
    assert blocked == frozenset({"if_else", "telegram_send"})
    errors = validate_solo_node(TelegramSendNode(id="tg", message="hi"))
    assert any("telegram_send" in item for item in errors)
