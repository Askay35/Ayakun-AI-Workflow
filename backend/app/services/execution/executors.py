from collections.abc import Awaitable, Callable
from decimal import Decimal

import httpx

from schemas.workflow import HttpRequestNode, IfElseNode, NodeType, PromptNode, TelegramSendNode, WebSearchNode
from services.execution.actions import (
    HttpRequestAction,
    IfElseAction,
    PromptAction,
    TelegramSendAction,
    WebSearchAction,
)
from services.execution.registry import NodeRegistry
from services.pricing import PricingService
from services.providers import ModelRouter, TelegramNotificationProvider, WebSearchRouter

BudgetProvider = Callable[[], Awaitable[Decimal]]


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

    async def web_search(self, node: WebSearchNode, context: dict) -> list:
        return await WebSearchAction(self.search_router, self.pricing, self.available_budget).execute(node, context)

    async def prompt(self, node: PromptNode, context: dict) -> dict:
        return await PromptAction(self.model_router, self.pricing, self.available_budget).execute(node, context)

    async def http_request(self, node: HttpRequestNode, context: dict) -> dict | list:
        return await HttpRequestAction(self.client).execute(node, context)

    async def telegram_send(self, node: TelegramSendNode, context: dict) -> dict:
        return await TelegramSendAction(self.notifications).execute(node, context)

    async def if_else(self, node: IfElseNode, context: dict) -> dict | list:
        return await IfElseAction().execute(node, context)

    def registry(self) -> NodeRegistry:
        registry = NodeRegistry()
        registry.register(NodeType.WEB_SEARCH, self.web_search)
        registry.register(NodeType.PROMPT, self.prompt)
        registry.register(NodeType.TELEGRAM_SEND, self.telegram_send)
        registry.register(NodeType.HTTP_REQUEST, self.http_request)
        registry.register(NodeType.IF_ELSE, self.if_else)
        return registry
