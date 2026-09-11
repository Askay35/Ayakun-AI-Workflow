from decimal import Decimal

import pytest

from services.pricing import (
    CREDIT_PROVIDER_COST_USD,
    CREDIT_SALE_PRICE_USD,
    DEFAULT_PRICES,
    MARGIN_MULTIPLIER,
    PricingService,
    billable_credits,
    estimate_run_cost,
    maximum_output_tokens,
    provider_cost_usd,
    usage_credits,
)
from execution.tasks import node_cost
from schemas.workflow import PromptNode, WebSearchNode, WorkflowGraph


def test_deepseek_flash_credit_conversion() -> None:
    price = DEFAULT_PRICES[("deepseek", "deepseek-v4-flash")]
    assert usage_credits(price, 1000, 0, 0) == Decimal("0.014")
    assert usage_credits(price, 0, 1000, 0) == Decimal("0.44")
    assert usage_credits(price, 0, 0, 1000) == Decimal("1.32")


def test_deepseek_pro_credit_conversion() -> None:
    price = DEFAULT_PRICES[("deepseek", "deepseek-v4-pro")]
    assert usage_credits(price, 1000, 0, 0) == Decimal("0.044")
    assert usage_credits(price, 0, 1000, 0) == Decimal("1.32")
    assert usage_credits(price, 0, 0, 1000) == Decimal("3.96")


def test_serper_costs_one_credit_per_search() -> None:
    assert DEFAULT_PRICES[("serper", "search")].search == Decimal("1")


def test_maximum_output_never_exceeds_budget() -> None:
    price = DEFAULT_PRICES[("deepseek", "deepseek-v4-flash")]
    budget = Decimal("2")
    output = maximum_output_tokens(price, budget, input_tokens=1000)
    worst_case = usage_credits(price, 0, 1000, output)
    assert worst_case <= budget
    assert usage_credits(price, 0, 1000, output + 1) > budget


def test_input_cost_can_exhaust_budget_without_api_call() -> None:
    price = DEFAULT_PRICES[("deepseek", "deepseek-v4-pro")]
    assert maximum_output_tokens(price, Decimal("0.65"), input_tokens=1000) == 0


def test_credit_economics_yield_fifty_percent_margin_at_peak() -> None:
    credits = Decimal("1000")
    peak_provider_cost = provider_cost_usd(credits)
    customer_price = credits * CREDIT_SALE_PRICE_USD
    assert MARGIN_MULTIPLIER == Decimal("2")
    assert CREDIT_PROVIDER_COST_USD == Decimal("0.001")
    assert CREDIT_SALE_PRICE_USD == Decimal("0.002")
    assert (customer_price - peak_provider_cost) / customer_price == Decimal("0.5")


def test_usage_charges_twice_offpeak_deepseek_cost() -> None:
    price = DEFAULT_PRICES[("deepseek", "deepseek-v4-flash")]
    credits = usage_credits(price, 0, 863, 4990)
    offpeak_usd = (Decimal("863") * Decimal("0.22") + Decimal("4990") * Decimal("0.66")) / Decimal("1000000")
    assert credits == Decimal("6.96652")
    assert credits * CREDIT_SALE_PRICE_USD == offpeak_usd * MARGIN_MULTIPLIER * MARGIN_MULTIPLIER
    assert credits * CREDIT_PROVIDER_COST_USD == offpeak_usd * MARGIN_MULTIPLIER


class FakePricing:
    async def get(self, provider: str, model: str):
        return DEFAULT_PRICES[(provider, model)]


@pytest.mark.asyncio
async def test_node_cost_uses_real_cache_and_output_usage() -> None:
    node = PromptNode(id="prompt", prompt="test", model="deepseek-v4-flash")
    output = {
        "model": "deepseek-v4-flash",
        "usage": {
            "input_cache_hit_tokens": 1000,
            "input_cache_miss_tokens": 1000,
            "output_tokens": 1000,
        },
        "truncated": True,
    }
    credits, units, details = await node_cost(FakePricing(), node, output)
    assert credits == Decimal("1.774000")
    assert units == 3000
    assert details["truncated"] is True
    assert Decimal(details["provider_cost_usd"]) == Decimal("0.001774")


def test_billable_credits_round_up() -> None:
    assert billable_credits(Decimal("0")) == Decimal("0")
    assert billable_credits(Decimal("0.01")) == Decimal("1")
    assert billable_credits(Decimal("1.00")) == Decimal("1")
    assert billable_credits(Decimal("1.01")) == Decimal("2")


@pytest.mark.asyncio
async def test_node_cost_keeps_fractional_llm_usage() -> None:
    node = PromptNode(id="prompt", prompt="test", model="deepseek-v4-flash")
    output = {
        "model": "deepseek-v4-flash",
        "usage": {
            "input_cache_miss_tokens": 100,
            "output_tokens": 50,
        },
    }
    credits, units, _ = await node_cost(FakePricing(), node, output)
    assert credits == Decimal("0.110000")
    assert units == 150


def test_search_plus_prompt_estimate_is_whole_credits() -> None:
    graph = WorkflowGraph(nodes=[
        WebSearchNode(id="search", query="новости", children=["prompt"]),
        PromptNode(id="prompt", prompt="Сделай вывод", parents=["search"]),
    ])
    assert estimate_run_cost(graph) == Decimal("2")


@pytest.mark.asyncio
async def test_estimate_graph_recognizes_enum_node_types() -> None:
    graph = WorkflowGraph(nodes=[
        WebSearchNode(id="search", query="новости", children=["prompt"]),
        PromptNode(id="prompt", prompt="Сделай вывод", parents=["search"]),
    ])
    assert str(graph.nodes[0].type).startswith("NodeType.")

    class Service(PricingService):
        def __init__(self) -> None:
            self.db = None  # type: ignore[assignment]

        async def get(self, provider: str, model: str):
            return DEFAULT_PRICES[(provider, model)]

    assert await Service().estimate_graph(graph) == Decimal("2")
