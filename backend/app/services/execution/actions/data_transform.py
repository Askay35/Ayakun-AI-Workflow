from __future__ import annotations

import json
from typing import Any

from helper import (
    apply_variable_assignments,
    evaluate_condition,
    json_root_from_output,
    render_template,
    _resolve_json_path,
    _MISSING,
    _substitute_placeholders,
)
from schemas.workflow import DataTransformNode
from services.execution.actions.base import NodeAction
from services.execution.context import incoming_payload, parent_records


def parse_field_list(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Список полей содержит некорректный JSON: {exc.msg}") from exc
        if not isinstance(parsed, list):
            raise ValueError("Список полей должен быть JSON-массивом")
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [part.strip() for part in text.split(",") if part.strip()]


def parse_mapping(raw: str, *_args: object) -> dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    if text.startswith("{") or text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Соответствие полей содержит некорректный JSON: {exc.msg}") from exc
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("Соответствие полей должно быть JSON-объектом")
    mapping: dict[str, Any] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped and ":" not in stripped:
            raise ValueError("Строка соответствия должна быть вида старое=новое")
        separator = "=" if "=" in stripped else ":"
        key, value = stripped.split(separator, 1)
        name = key.strip()
        if not name:
            continue
        mapping[name] = value.strip()
    return mapping


def _extract_path(data: object, path: str) -> object:
    text = (path or "").strip()
    if not text:
        return data
    resolved = _resolve_json_path(data, text)
    if resolved is _MISSING:
        raise ValueError(f"В данных нет поля {text}")
    return resolved


def _require_object(item: object, operation: str) -> dict:
    if not isinstance(item, dict):
        raise ValueError(f"{operation}: ожидается объект или массив объектов")
    return item


def _items(data: object) -> tuple[list[object], bool]:
    if isinstance(data, list):
        return list(data), True
    return [data], False


def _select(data: object, fields: list[str]) -> object:
    if not fields:
        raise ValueError("Укажите поля для Select")
    items, was_list = _items(data)
    selected = [{key: _require_object(item, "Select").get(key) for key in fields} for item in items]
    return selected if was_list else selected[0]


def _rename(data: object, mapping: dict[str, Any]) -> object:
    if not mapping:
        raise ValueError("Укажите соответствия для Rename")
    items, was_list = _items(data)
    renamed: list[dict] = []
    for item in items:
        record = dict(_require_object(item, "Rename"))
        for old, new in mapping.items():
            name = str(new)
            if old in record:
                record[name] = record.pop(old)
        renamed.append(record)
    return renamed if was_list else renamed[0]


def _set_fields(data: object, mapping: dict[str, Any], variables: dict) -> object:
    if not mapping:
        raise ValueError("Укажите значения для Set")
    items, was_list = _items(data)
    updated: list[dict] = []
    for item in items:
        record = dict(_require_object(item, "Set"))
        root = json_root_from_output(record)
        for key, raw in mapping.items():
            record[str(key)] = _substitute_placeholders(raw, root, variables) if isinstance(raw, str) else raw
        updated.append(record)
    return updated if was_list else updated[0]


def _remove(data: object, fields: list[str]) -> object:
    if not fields:
        raise ValueError("Укажите поля для Remove")
    drop = set(fields)
    items, was_list = _items(data)
    cleaned = [{key: value for key, value in _require_object(item, "Remove").items() if key not in drop} for item in items]
    return cleaned if was_list else cleaned[0]


def _filter(data: object, condition: str, variables: dict) -> list:
    if not (condition or "").strip():
        raise ValueError("Укажите условие для Filter")
    items, _was_list = _items(data)
    kept: list[object] = []
    for item in items:
        root = json_root_from_output(item)
        if evaluate_condition(condition, root, variables):
            kept.append(item)
    return kept


def _sort_key(item: object, field: str) -> tuple[int, object]:
    if isinstance(item, dict):
        value = item.get(field)
    else:
        value = item
    if value is None:
        return (1, "")
    return (0, value)


def _sort(data: object, field: str, direction: str) -> list:
    if not (field or "").strip():
        raise ValueError("Укажите поле для Sort")
    if not isinstance(data, list):
        raise ValueError("Sort ожидает массив")
    reverse = direction == "desc"
    return sorted(data, key=lambda item: _sort_key(item, field), reverse=reverse)


def _map_items(data: object, mapping: dict[str, Any] | str, variables: dict) -> object:
    if mapping == {} or mapping == "":
        raise ValueError("Укажите шаблон для Map")
    items, was_list = _items(data)
    mapped: list[object] = []
    for item in items:
        root = json_root_from_output(item)
        mapped.append(_substitute_placeholders(mapping, root, variables))
    return mapped if was_list else mapped[0]


def _deep_merge(target: dict, source: dict) -> dict:
    for key, value in source.items():
        current = target.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            target[key] = _deep_merge(dict(current), value)
        else:
            target[key] = value
    return target


def _merge_sources(node: DataTransformNode, context: dict) -> list[object]:
    """Что объединять: выходы всех входящих узлов или элементы массива единственного входа."""
    records = parent_records(node, context)
    if len(records) > 1:
        return [_extract_path(json_root_from_output(record.get("output")), node.path) for record in records]
    data = _extract_path(incoming_payload(node, context), node.path)
    return list(data) if isinstance(data, list) else [data]


def _merge(node: DataTransformNode, context: dict, variables: dict) -> dict:
    merged: dict = {}
    for item in _merge_sources(node, context):
        if item is None:
            continue
        if not isinstance(item, dict):
            raise ValueError("Merge: объединять можно только объекты")
        merged = _deep_merge(merged, item)
    extra = parse_mapping(node.mapping_json)
    if extra:
        merged = _set_fields(merged, extra, variables)
    if not merged:
        raise ValueError("Merge: нет данных для объединения")
    return merged


class DataTransformAction(NodeAction):
    async def execute(self, node: DataTransformNode, context: dict) -> dict | list:
        if node.operation == "merge":
            output = _merge(node, context, context.setdefault("variables", {}))
            apply_variable_assignments(node.assignments, output, context)
            return output
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})
        data = _extract_path(payload, node.path)
        operation = node.operation
        if operation == "select":
            output: dict | list = _select(data, parse_field_list(node.fields))
        elif operation == "rename":
            output = _rename(data, parse_mapping(node.mapping_json, payload, variables))
        elif operation == "set":
            output = _set_fields(data, parse_mapping(node.mapping_json, payload, variables), variables)
        elif operation == "remove":
            output = _remove(data, parse_field_list(node.fields))
        elif operation == "filter":
            output = _filter(data, node.condition, variables)
        elif operation == "sort":
            output = _sort(data, render_template(node.sort_field, payload, variables).strip(), node.sort_direction)
        elif operation == "map":
            mapping: dict[str, Any] | str
            text = (node.mapping_json or "").strip()
            if text.startswith("{") or text.startswith("["):
                try:
                    mapping = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Шаблон Map содержит некорректный JSON: {exc.msg}") from exc
            else:
                mapping = parse_mapping(text, payload, variables)
            output = _map_items(data, mapping, variables)
        else:
            raise ValueError("Неизвестная операция преобразования")
        apply_variable_assignments(node.assignments, output, context)
        return output
