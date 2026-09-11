"""Исполнители узлов workflow: поиск, обработка, Telegram.

Вызываются из worker через NodeRegistry.
Вывод родительских узлов берётся из node.parents и context["nodes"].
"""

from collections.abc import Awaitable, Callable
from decimal import Decimal
import json

import httpx

from helper import evaluate_condition, expression_root, form_request_body, json_root_from_output
from core.config import settings
from schemas.workflow import HttpRequestNode, IfElseNode, Node, NodeType, PromptNode, TelegramSendNode, WebSearchNode
from services.providers import (
    ModelRouter,
    SearchResult,
    TelegramNotificationProvider,
    WebSearchRouter,
    llm_instructions,
)
from services.pricing import PricingService, maximum_output_tokens
from utils.deepseek_tokenizer import count_prompt_tokens

Executor = Callable[[object, dict], Awaitable[object]]
BudgetProvider = Callable[[], Awaitable[Decimal]]
TELEGRAM_TEXT_LIMIT = 4096


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
            return json.dumps(output, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(output)
    if isinstance(output, list):
        chunks: list[str] = []
        for item in output:
            data = item.model_dump() if hasattr(item, "model_dump") else item
            if isinstance(data, dict):
                title = data.get("title") or ""
                snippet = data.get("snippet") or ""
                url = data.get("url") or ""
                item_date = data.get("date") or ""
                chunk = "\n".join(part for part in (title, snippet, url, item_date) if part)
                if chunk:
                    chunks.append(chunk)
            elif isinstance(data, str) and data.strip():
                chunks.append(data)
        return "\n\n".join(chunks)
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


class NodeRegistry:
    """type узла → async executor(node, context) -> output."""

    def __init__(self):
        self._executors: dict[str, Executor] = {}

    def register(self, node_type: str, executor: Executor) -> None:
        self._executors[node_type] = executor

    async def execute(self, node: object, context: dict) -> object:
        executor = self._executors.get(getattr(node, "type"))
        if not executor:
            raise ValueError(f"Нет executor для {getattr(node, 'type')}")
        return await executor(node, context)


class DefaultExecutors:
    def __init__(
        self,
        client: httpx.AsyncClient,
        pricing: PricingService,
        available_budget: BudgetProvider,
    ):
        self.model_router = ModelRouter()
        self.search_router = WebSearchRouter(client)
        self.notifications = TelegramNotificationProvider(client)
        self.pricing = pricing
        self.available_budget = available_budget
        self.client = client

    async def web_search(self, node: WebSearchNode, context: dict) -> list[SearchResult]:
        price = await self.pricing.get("serper", "search")
        if await self.available_budget() < price.search:
            raise ValueError("Недостаточно credits для поискового запроса")
        provider = self.search_router.select()
        results = await provider.search(node.query, node.period)
        return results

    async def prompt(self, node: PromptNode, context: dict) -> dict:
        provider, default_model = self.model_router.select(
            node.provider,
            operation=node.complexity,
        )
        setting_key = "complex_llm_model" if node.complexity == "complex_text" else "simple_llm_model"
        model = node.model or await self.pricing.setting(setting_key, default_model)
        composed_instructions = llm_instructions(node.instructions or None, node.output_format or None)
        input_data = parent_output_texts(node, context) or None
        input_tokens = count_prompt_tokens(
            node.prompt,
            instructions=composed_instructions,
            input_data=input_data,
        )
        price = await self.pricing.get("deepseek", model)
        configured_max = int(await self.pricing.setting(
            "llm_max_output_tokens", settings.llm_max_output_tokens
        ))
        max_tokens = min(
            maximum_output_tokens(price, await self.available_budget(), input_tokens),
            configured_max,
        )
        if max_tokens < 1:
            raise ValueError("Недостаточно credits даже для входных токенов LLM-запроса")
        result = await provider.prompt(
            node.prompt,
            instructions=node.instructions or None,
            output_format=node.output_format or None,
            input_data=input_data,
            model=model,
            max_tokens=max_tokens,
        )
        return result.model_dump(mode="json")

    async def http_request(self, node: HttpRequestNode, context: dict) -> dict | list:
        records = parent_records(node, context)
        if len(records) != 1:
            raise ValueError("HTTP Request принимает ровно одну входящую связь")
        request_data = form_request_body(
            node.request_json,
            json_root_from_output(records[0].get("output")),
        )
        method = str(request_data.get("method") or "GET").upper()
        url = request_data.get("url")
        if not isinstance(url, str) or not url.strip():
            raise ValueError("В данных запроса не указан url")
        headers = request_data.get("headers") or {}
        if headers and not isinstance(headers, dict):
            raise ValueError("headers в данных запроса должны быть JSON-объектом")
        body = request_data.get("body")
        kwargs: dict = {
            "method": method,
            "url": url.strip(),
            "headers": headers,
            "timeout": settings.provider_timeout_seconds,
        }
        if body is not None:
            kwargs["json"] = body
        response = await self.client.request(**kwargs)
        if response.is_error:
            snippet = (response.text or "")[:500]
            raise ValueError(f"HTTP {response.status_code}: {snippet or 'ошибка запроса'}")
        if not response.content:
            return {"status": response.status_code}
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return {"status": response.status_code, "text": response.text}
        if isinstance(payload, (dict, list)):
            return payload
        return {"data": payload}

    async def telegram_send(self, node: TelegramSendNode, context: dict) -> dict:
        chat_id = node.chat_id or context.get("input", {}).get("chat_id")
        texts = parent_output_texts(node, context)
        message = texts[0] if texts else ""
        if not message:
            return {"sent": False, "text": ""}
        if not chat_id:
            raise ValueError("telegram_send требует chat_id")
        if len(message) > TELEGRAM_TEXT_LIMIT:
            message = message[: TELEGRAM_TEXT_LIMIT - 1] + "…"
        await self.notifications.send(str(chat_id), message)
        return {"sent": True, "text": message}

    async def if_else(self, node: IfElseNode, context: dict) -> dict | list:
        records = parent_records(node, context)
        if len(records) != 1:
            raise ValueError("IF ELSE принимает ровно одну входящую связь")
        payload = expression_root(records[0].get("output"))
        taken = evaluate_condition(node.condition, payload)
        context.setdefault("taken_branches", {})[node.id] = "true" if taken else "false"
        if isinstance(payload, dict):
            return dict(payload)
        if isinstance(payload, list):
            return list(payload)
        return {"value": payload}

    def registry(self) -> NodeRegistry:
        registry = NodeRegistry()
        registry.register(NodeType.WEB_SEARCH, self.web_search)
        registry.register(NodeType.PROMPT, self.prompt)
        registry.register(NodeType.TELEGRAM_SEND, self.telegram_send)
        registry.register(NodeType.HTTP_REQUEST, self.http_request)
        registry.register(NodeType.IF_ELSE, self.if_else)
        return registry
