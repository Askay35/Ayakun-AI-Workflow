import json

from helper import json_root_from_output
from schemas.workflow import Node, NodeType


def node_type_value(value: object) -> str:
    """Каноническое значение типа узла: 'web_search', не 'NodeType.WEB_SEARCH'."""
    if isinstance(value, NodeType):
        return value.value
    raw = getattr(value, "value", value)
    text = str(raw or "")
    if text.startswith("NodeType."):
        member = NodeType.__members__.get(text.split(".", 1)[1])
        if member is not None:
            return member.value
    return text


def output_text(output: object) -> str:
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    if hasattr(output, "text") and isinstance(output.text, str):
        return output.text
    if isinstance(output, dict):
        for key in ("text", "answer", "content"):
            value = output.get(key)
            if isinstance(value, str) and value.strip():
                return value
        try:
            return json.dumps(output, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(output)
    if isinstance(output, list):
        try:
            return json.dumps(output, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(output)
    return str(output)


def parent_records(node: Node, context: dict) -> list[dict]:
    nodes = context.get("nodes") or {}
    records: list[dict] = []
    for parent_id in node.parents:
        record = nodes.get(parent_id)
        if isinstance(record, dict):
            records.append(record)
    return records


def parent_output_texts(node: Node, context: dict) -> list[str]:
    """Текст только напрямую связанных родителей (`node.parents`), не всего графа."""
    allowed = {item.value for item in NodeType.with_output()}
    texts: list[str] = []
    for record in parent_records(node, context):
        if node_type_value(record.get("type")) not in allowed:
            continue
        text = output_text(record.get("output")).strip()
        if text:
            texts.append(text)
    return texts


def incoming_payload(node: Node, context: dict) -> object:
    """Корень JSON предыдущего узла или вход запуска, если родителей нет."""
    records = parent_records(node, context)
    if len(records) > 1:
        raise ValueError("Узел может иметь только одну входящую связь")
    if records:
        return json_root_from_output(records[0].get("output"))
    return json_root_from_output(context.get("input") or {})
