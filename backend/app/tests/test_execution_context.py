from schemas.workflow import NodeType, PromptNode
from services.execution import node_type_value, output_text, parent_output_texts


def test_node_type_value_normalizes_enum_str() -> None:
    assert node_type_value(NodeType.WEB_SEARCH) == "web_search"
    assert node_type_value(str(NodeType.WEB_SEARCH)) == "web_search"
    assert node_type_value("web_search") == "web_search"


def test_parent_output_includes_search_results_even_if_type_was_str_enum() -> None:
    node = PromptNode(id="prompt", prompt="Сделай вывод", parents=["search"])
    context = {
        "nodes": {
            "search": {
                "type": str(NodeType.WEB_SEARCH),
                "output": [
                    {"title": "Новость", "snippet": "Коротко о событии", "url": "https://example.com"}
                ],
            }
        }
    }
    texts = parent_output_texts(node, context)
    assert len(texts) == 1
    assert "Новость" in texts[0]
    assert "Коротко о событии" in texts[0]


def test_output_text_joins_search_hits() -> None:
    text = output_text([
        {"title": "A", "snippet": "one", "url": "https://a.example"},
        {"title": "B", "snippet": "two", "url": "https://b.example"},
    ])
    assert '"title": "A"' in text
    assert '"title": "B"' in text
    assert "snippet" in text


def test_parent_output_uses_only_direct_parents() -> None:
    node = PromptNode(id="prompt", prompt="Сделай вывод", parents=["search"])
    context = {
        "nodes": {
            "search": {
                "type": "web_search",
                "output": [{"title": "Прямой", "snippet": "ok", "url": "https://direct.example"}],
            },
            "other": {
                "type": "web_search",
                "output": [{"title": "Чужой", "snippet": "no", "url": "https://other.example"}],
            },
        }
    }
    texts = parent_output_texts(node, context)
    combined = "\n".join(texts)
    assert "Прямой" in combined
    assert "Чужой" not in combined
