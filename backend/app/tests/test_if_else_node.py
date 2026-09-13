import json

import pytest

from helper import evaluate_condition
from schemas.workflow import IfElseNode, PromptNode, TelegramSendNode, WorkflowGraph
from execution.tasks import WorkflowRunExecutor
from services.execution import DefaultExecutors
from services.workflow import validate_graph


def test_condition_greater_than_true() -> None:
    assert evaluate_condition('{{$json.score}} > 0.8', {"score": 0.9}) is True


def test_condition_greater_than_false() -> None:
    assert evaluate_condition('{{$json.score}} > 0.8', {"score": 0.5}) is False


def test_condition_string_equals() -> None:
    assert evaluate_condition('{{$json.status}} == "active"', {"status": "active"}) is True
    assert evaluate_condition('{{$json.name}} == "John"', {"name": "Jane"}) is False


def test_condition_boolean_and_null() -> None:
    assert evaluate_condition('{{$json.active}} == true', {"active": True}) is True
    assert evaluate_condition('{{$json.deleted}} != true', {"deleted": False}) is True
    assert evaluate_condition('{{$json.email}} != null', {"email": "a@b.c"}) is True
    assert evaluate_condition('{{$json.email}} != null', {"email": None}) is False


def test_condition_empty_and_invalid() -> None:
    with pytest.raises(ValueError, match="условие не задано"):
        evaluate_condition("  ", {"score": 1})
    with pytest.raises(ValueError, match="некорректное условие"):
        evaluate_condition('{{$json.status}} ===', {"status": "active"})


def test_condition_missing_field() -> None:
    data = {"score": 1}
    assert evaluate_condition('{{$json.nonexistent}} == null', data) is True
    assert evaluate_condition('{{$json.nonexistent}} == undefined', data) is True
    assert evaluate_condition('{{$json.nonexistent}} != null', data) is False
    assert evaluate_condition('{{$json.nonexistent}} != undefined', data) is False
    assert evaluate_condition('{{$json.nonexistent}} == "test"', data) is False
    assert evaluate_condition('{{$json.nonexistent}}', data) is False
    assert evaluate_condition('{{$json.score}}', data) is True
    with pytest.raises(ValueError, match="нельзя сравнить"):
        evaluate_condition('{{$json.nonexistent}} > 1', data)


def test_condition_array_path() -> None:
    assert evaluate_condition('{{$data[0].price}} > 100', {"data": [{"price": 123}]}) is True
    assert evaluate_condition('{{$data.0.price}} == 123', {"data": [{"price": 123}]}) is True


def test_if_else_graph_requires_both_branches() -> None:
    graph = WorkflowGraph(nodes=[
        PromptNode(id="prompt", prompt="ok", children=["iff"]),
        IfElseNode(
            id="iff",
            condition='{{$json.score}} >= 0.8',
            parents=["prompt"],
            true_children=["tg_true"],
            false_children=["tg_false"],
            children=["tg_true", "tg_false"],
        ),
        TelegramSendNode(id="tg_true", parents=["iff"]),
        TelegramSendNode(id="tg_false", parents=["iff"]),
    ])
    assert validate_graph(graph, strict=True) == []


@pytest.mark.asyncio
async def test_if_else_executor_passes_input_through() -> None:
    executors = object.__new__(DefaultExecutors)
    node = IfElseNode(
        id="iff",
        condition='{{$json.score}} >= 0.8',
        parents=["prompt"],
        true_children=["a"],
        false_children=["b"],
    )
    payload = {"userId": "123", "email": "test@example.com", "score": 0.91}
    parent_output = {"text": json.dumps(payload), "usage": {"output_tokens": 4}}
    context = {
        "nodes": {
            "prompt": {
                "type": "prompt",
                "output": parent_output,
            }
        },
        "taken_branches": {},
    }
    result = await executors.if_else(node, context)
    assert result == parent_output
    assert context["taken_branches"]["iff"] == "true"

    false_output = {"text": json.dumps({**payload, "score": 0.5}), "usage": {"output_tokens": 4}}
    context["nodes"]["prompt"]["output"] = false_output
    result = await executors.if_else(node, context)
    assert result == false_output
    assert context["taken_branches"]["iff"] == "false"


@pytest.mark.asyncio
async def test_if_else_passes_http_payload_unchanged() -> None:
    executors = object.__new__(DefaultExecutors)
    node = IfElseNode(
        id="iff",
        condition='{{$data[0].price}} > 100',
        parents=["http"],
        true_children=["a"],
        false_children=["b"],
    )
    parent_output = {"data": [{"price": 123}]}
    context = {
        "nodes": {
            "http": {
                "type": "http_request",
                "output": parent_output,
            }
        },
        "taken_branches": {},
    }
    result = await executors.if_else(node, context)
    assert result == parent_output
    assert result is not parent_output
    assert context["taken_branches"]["iff"] == "true"


def test_unselected_branch_is_not_reachable() -> None:
    executor = object.__new__(WorkflowRunExecutor)
    context = {"nodes": {"iff": {"type": "if_else", "output": {"score": 0.91}}}}
    blocked = {("iff", "tg_false")}
    assert executor._is_reachable(TelegramSendNode(id="tg_true", parents=["iff"]), context, blocked) is True
    assert executor._is_reachable(TelegramSendNode(id="tg_false", parents=["iff"]), context, blocked) is False
