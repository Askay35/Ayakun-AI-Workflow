"""Цикл выполняется внутри узла и отдаёт {items, count}.

Потомки графа не запускаются по разу на итерацию: у исполнителя нет отдельного
крюка под подграф. Переменные между итерациями while не меняются, поэтому
условие, которое остаётся истинным, останавливается на LOOP_MAX_ITERATIONS.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from helper import evaluate_condition, resolve_operand
from schemas.workflow import LoopNode
from services.execution.actions.base import NodeAction
from services.execution.context import incoming_payload

LOOP_MAX_ITERATIONS = 100


def _as_list(value: object) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return parsed
    raise ValueError("Цикл: источник должен быть массивом")


def _as_count(value: object) -> int:
    if isinstance(value, bool) or value is None:
        raise ValueError("Цикл: число повторов должно быть не меньше 1")
    try:
        number = int(Decimal(str(value)))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Цикл: число повторов должно быть не меньше 1") from exc
    if number < 1:
        raise ValueError("Цикл: число повторов должно быть не меньше 1")
    return number


class LoopAction(NodeAction):
    async def execute(self, node: LoopNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})
        capped = False
        if node.mode == "for_each":
            source = (node.source or "").strip()
            if not source:
                raise ValueError("Цикл: укажите источник массива")
            resolved = resolve_operand(source, payload, variables=variables)
            items = _as_list(resolved)
            if len(items) > LOOP_MAX_ITERATIONS:
                items = items[:LOOP_MAX_ITERATIONS]
                capped = True
        elif node.mode == "times":
            raw = (node.times or "").strip()
            if not raw:
                raise ValueError("Цикл: укажите число повторов")
            count = _as_count(resolve_operand(raw, payload, variables=variables))
            if count > LOOP_MAX_ITERATIONS:
                count = LOOP_MAX_ITERATIONS
                capped = True
            items = list(range(1, count + 1))
        else:
            name = (node.while_variable or "").strip()
            if not name:
                raise ValueError("Цикл: выберите переменную")
            right = (node.while_value or "").strip()
            if not right:
                raise ValueError("Цикл: укажите значение сравнения")
            condition = f"{{{{{name}}}}} {node.while_operator} {right}"
            items = []
            for index in range(1, LOOP_MAX_ITERATIONS + 1):
                # index доступен шаблону правой части как {{loop_index}}, без подграфа.
                scoped = dict(variables)
                scoped["loop_index"] = index
                if not evaluate_condition(condition, payload, scoped):
                    break
                items.append({"index": index, "item": variables.get(name)})
            else:
                capped = True
        return {
            "mode": node.mode,
            "items": items,
            "count": len(items),
            "capped": capped,
        }
