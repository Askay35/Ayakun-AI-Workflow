from __future__ import annotations

import asyncio
from decimal import Decimal, InvalidOperation

from helper import resolve_operand
from schemas.workflow import DelayNode
from services.execution.actions.base import NodeAction
from services.execution.context import incoming_payload

_MAX_SECONDS = Decimal("3600")
_MAX_MINUTES = Decimal("60")


def clamp_delay(amount: object, unit: str) -> tuple[Decimal, Decimal]:
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Задержка: некорректная длительность") from exc
    if unit == "minutes":
        clamped = min(_MAX_MINUTES, max(Decimal("0"), value))
        return clamped, (clamped * Decimal("60")).quantize(Decimal("0.001"))
    clamped = min(_MAX_SECONDS, max(Decimal("0"), value))
    return clamped, clamped.quantize(Decimal("0.001"))


class DelayAction(NodeAction):
    async def execute(self, node: DelayNode, context: dict) -> dict:
        payload = incoming_payload(node, context)
        variables = context.setdefault("variables", {})
        raw = (node.amount or "").strip()
        if not raw:
            raise ValueError("Задержка: укажите длительность")
        resolved = resolve_operand(raw, payload, variables=variables)
        amount, waited = clamp_delay(resolved, node.unit)
        await asyncio.sleep(float(waited))
        return {
            "waited_seconds": float(waited),
            "amount": float(amount),
            "unit": node.unit,
        }
