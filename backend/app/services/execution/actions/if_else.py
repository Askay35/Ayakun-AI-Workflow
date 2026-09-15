from helper import evaluate_condition, expression_root
from schemas.workflow import IfElseNode
from services.execution.actions.base import NodeAction
from services.execution.context import parent_records


def _passthrough(parent_output: object) -> dict | list:
    if isinstance(parent_output, dict):
        return dict(parent_output)
    if isinstance(parent_output, list):
        return list(parent_output)
    if isinstance(parent_output, str):
        return {"text": parent_output}
    if parent_output is None:
        return {}
    return {"value": parent_output}


class IfElseAction(NodeAction):
    async def execute(self, node: IfElseNode, context: dict) -> dict | list:
        records = parent_records(node, context)
        if len(records) != 1:
            raise ValueError("IF ELSE принимает ровно одну входящую связь")
        parent_output = records[0].get("output")
        payload = expression_root(parent_output)
        taken = evaluate_condition(node.condition, payload, context.setdefault("variables", {}))
        branch = "TRUE" if taken else "FALSE"
        context.setdefault("taken_branches", {})[node.id] = "true" if taken else "false"
        condition = (node.condition or "").strip()
        return {
            "condition": condition,
            "result": taken,
            "branch": branch,
            "text": f"{condition}\n{branch}",
            "passthrough": _passthrough(parent_output),
        }
