from collections.abc import Awaitable, Callable
from decimal import Decimal

import httpx

from schemas.workflow import (
    DataTransformNode,
    EmailNode,
    GoogleSheetsNode,
    HttpRequestNode,
    IfElseNode,
    NodeType,
    PromptNode,
    SqlQueryNode,
    TelegramSendNode,
    WebhookNode,
    WebSearchNode,
)
from services.execution.actions import (
    DataTransformAction,
    EmailAction,
    GoogleSheetsAction,
    HttpRequestAction,
    IfElseAction,
    PromptAction,
    SqlQueryAction,
    TelegramSendAction,
    WebSearchAction,
    WebhookAction,
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
        variables: dict | None = None,
    ):
        self.model_router = ModelRouter()
        self.search_router = WebSearchRouter(client)
        self.notifications = TelegramNotificationProvider(client)
        self.pricing = pricing
        self.available_budget = available_budget
        self.client = client
        self.variables = dict(variables or {})

    def prepare(self, context: dict) -> dict:
        context.setdefault("variables", dict(getattr(self, "variables", None) or {}))
        return context

    async def web_search(self, node: WebSearchNode, context: dict) -> list:
        return await WebSearchAction(self.search_router, self.pricing, self.available_budget).execute(node, self.prepare(context))

    async def prompt(self, node: PromptNode, context: dict) -> dict:
        return await PromptAction(self.model_router, self.pricing, self.available_budget).execute(node, self.prepare(context))

    async def http_request(self, node: HttpRequestNode, context: dict) -> dict | list:
        return await HttpRequestAction(self.client).execute(node, self.prepare(context))

    async def telegram_send(self, node: TelegramSendNode, context: dict) -> dict:
        return await TelegramSendAction(self.notifications).execute(node, self.prepare(context))

    async def if_else(self, node: IfElseNode, context: dict) -> dict | list:
        return await IfElseAction().execute(node, self.prepare(context))

    async def webhook(self, node: WebhookNode, context: dict) -> dict:
        return await WebhookAction().execute(node, self.prepare(context))

    async def google_sheets(self, node: GoogleSheetsNode, context: dict) -> dict:
        return await GoogleSheetsAction(self.client).execute(node, self.prepare(context))

    async def email(self, node: EmailNode, context: dict) -> dict:
        return await EmailAction().execute(node, self.prepare(context))

    async def data_transform(self, node: DataTransformNode, context: dict) -> dict | list:
        return await DataTransformAction().execute(node, self.prepare(context))

    async def sql_query(self, node: SqlQueryNode, context: dict) -> dict:
        return await SqlQueryAction().execute(node, self.prepare(context))

    def registry(self) -> NodeRegistry:
        registry = NodeRegistry()
        registry.register(NodeType.WEB_SEARCH, self.web_search)
        registry.register(NodeType.PROMPT, self.prompt)
        registry.register(NodeType.TELEGRAM_SEND, self.telegram_send)
        registry.register(NodeType.HTTP_REQUEST, self.http_request)
        registry.register(NodeType.IF_ELSE, self.if_else)
        registry.register(NodeType.WEBHOOK, self.webhook)
        registry.register(NodeType.GOOGLE_SHEETS, self.google_sheets)
        registry.register(NodeType.EMAIL, self.email)
        registry.register(NodeType.DATA_TRANSFORM, self.data_transform)
        registry.register(NodeType.SQL_QUERY, self.sql_query)
        return registry
