from decimal import Decimal

from schemas.workflow import WebSearchNode
from services.execution.actions.base import NodeAction
from services.pricing import PricingService
from services.providers import SearchResult, WebSearchRouter


class WebSearchAction(NodeAction):
    def __init__(
        self,
        search_router: WebSearchRouter,
        pricing: PricingService,
        available_budget,
    ):
        self.search_router = search_router
        self.pricing = pricing
        self.available_budget = available_budget

    async def execute(self, node: WebSearchNode, context: dict) -> list[SearchResult]:
        price = await self.pricing.get("serper", "search")
        if await self.available_budget() < price.search:
            raise ValueError("Недостаточно credits для поискового запроса")
        provider = self.search_router.select()
        results = await provider.search(node.query, node.period)
        return results
