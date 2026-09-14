from decimal import Decimal
from math import ceil
from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException

from models.billing import BillingReservation, Wallet, WalletLedger
from services.billing import BillingService
from services.pricing import (
    CREDIT_PROVIDER_COST_USD,
    CREDIT_SALE_PRICE_USD,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_PRICES,
    INPUT_TOKEN_PADDING,
    INPUT_TOKEN_SAFETY_RATIO,
    MARGIN_MULTIPLIER,
    PricingService,
    _estimated_prompt_input_tokens,
    billable_credits,
    billed_credits,
    estimate_run_cost,
    maximum_output_tokens,
    node_estimate,
    padded_input_tokens,
    provider_cost_usd,
    usage_credits,
)
from execution.tasks import node_cost
from schemas.workflow import PromptNode, WebSearchNode, WorkflowGraph


def test_deepseek_flash_credit_conversion() -> None:
    price = DEFAULT_PRICES[("deepseek", "deepseek-flash")]
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


def test_legacy_v4_flash_alias_uses_canonical_price() -> None:
    assert DEFAULT_PRICES[("deepseek", "deepseek-v4-flash")] is DEFAULT_PRICES[("deepseek", "deepseek-flash")]
    assert DEFAULT_PRICES[("deepseek", "deepseek-flash")].model == "deepseek-flash"


def test_billed_credits_applies_multiplier() -> None:
    price = DEFAULT_PRICES[("deepseek", "deepseek-flash")]
    assert billed_credits(price, 0, 1000, 0) == Decimal("0.880000")
    assert billed_credits(price, 1000, 1000, 1000) == Decimal("3.548000")


def test_maximum_output_never_exceeds_billed_budget() -> None:
    price = DEFAULT_PRICES[("deepseek", "deepseek-flash")]
    budget = Decimal("2")
    output = maximum_output_tokens(price, budget, input_tokens=1000)
    assert billed_credits(price, 0, 1000, output) <= budget
    assert billed_credits(price, 0, 1000, output + 1) > budget


def test_input_cost_can_exhaust_budget_without_api_call() -> None:
    price = DEFAULT_PRICES[("deepseek", "deepseek-v4-pro")]
    assert maximum_output_tokens(price, Decimal("0.65"), input_tokens=1000) == 0
    flash = DEFAULT_PRICES[("deepseek", "deepseek-flash")]
    assert billed_credits(flash, 0, 1000, 0) == Decimal("0.880000")
    assert maximum_output_tokens(flash, Decimal("0.80"), input_tokens=1000) == 0


def test_credit_economics_yield_fifty_percent_margin_at_peak() -> None:
    credits = Decimal("1000")
    peak_provider_cost = provider_cost_usd(credits)
    customer_price = credits * CREDIT_SALE_PRICE_USD
    assert MARGIN_MULTIPLIER == Decimal("2")
    assert CREDIT_PROVIDER_COST_USD == Decimal("0.001")
    assert CREDIT_SALE_PRICE_USD == Decimal("0.002")
    assert (customer_price - peak_provider_cost) / customer_price == Decimal("0.5")


def test_usage_charges_twice_offpeak_deepseek_cost() -> None:
    price = DEFAULT_PRICES[("deepseek", "deepseek-flash")]
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
    node = PromptNode(id="prompt", prompt="test", model="deepseek-flash")
    output = {
        "model": "deepseek-flash",
        "usage": {
            "input_cache_hit_tokens": 1000,
            "input_cache_miss_tokens": 1000,
            "output_tokens": 1000,
        },
        "truncated": True,
    }
    credits, units, details = await node_cost(FakePricing(), node, output)
    assert credits == Decimal("3.548000")
    assert units == 3000
    assert details["truncated"] is True
    assert Decimal(details["provider_cost_usd"]) == Decimal("0.003548")


def test_billable_credits_round_up() -> None:
    assert billable_credits(Decimal("0")) == Decimal("0")
    assert billable_credits(Decimal("0.01")) == Decimal("1")
    assert billable_credits(Decimal("1.00")) == Decimal("1")
    assert billable_credits(Decimal("1.01")) == Decimal("2")


@pytest.mark.asyncio
async def test_node_cost_keeps_fractional_llm_usage() -> None:
    node = PromptNode(id="prompt", prompt="test", model="deepseek-flash")
    output = {
        "model": "deepseek-flash",
        "usage": {
            "input_cache_miss_tokens": 100,
            "output_tokens": 50,
        },
    }
    credits, units, _ = await node_cost(FakePricing(), node, output)
    assert credits == Decimal("0.220000")
    assert units == 150


def test_padded_input_tokens_adds_safety_margin() -> None:
    assert padded_input_tokens(0) == 0
    assert padded_input_tokens(100) == 100 + max(INPUT_TOKEN_PADDING, ceil(100 * float(INPUT_TOKEN_SAFETY_RATIO)))
    assert padded_input_tokens(1000) == 1150


def test_prompt_estimate_includes_tokenizer_input_and_output() -> None:
    node = PromptNode(id="prompt", prompt="Сделай вывод")
    price = DEFAULT_PRICES[("deepseek", "deepseek-flash")]
    input_tokens = _estimated_prompt_input_tokens(node)
    expected = billable_credits(billed_credits(price, 0, input_tokens, DEFAULT_MAX_OUTPUT_TOKENS))
    assert node_estimate(node) == expected
    assert expected > billed_credits(price, 0, input_tokens, 0)
    assert input_tokens > 0
    assert node.max_output_tokens == DEFAULT_MAX_OUTPUT_TOKENS


def test_prompt_max_output_tokens_changes_max_cost() -> None:
    short = PromptNode(id="prompt", prompt="Сделай вывод", max_output_tokens=100)
    full = PromptNode(id="prompt", prompt="Сделай вывод", max_output_tokens=8000)
    assert node_estimate(short) < node_estimate(full)
    assert node_estimate(short) >= 1


def test_search_plus_prompt_estimate_uses_tokens_not_one_per_node() -> None:
    graph = WorkflowGraph(nodes=[
        WebSearchNode(id="search", query="новости", children=["prompt"]),
        PromptNode(id="prompt", prompt="Сделай вывод", parents=["search"]),
    ])
    cost = estimate_run_cost(graph)
    assert cost == Decimal("1") + node_estimate(graph.nodes[1], graph)
    assert cost != Decimal("2")
    assert cost > Decimal("1")


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

    assert await Service().estimate_graph(graph) == estimate_run_cost(graph)


class ChargeFakeDB:
    def __init__(self) -> None:
        self.wallet = Wallet(user_id=1, balance=Decimal("10"), reserved=Decimal("4"))
        self.reservation = BillingReservation(
            user_id=1,
            workflow_run_id=uuid.uuid4(),
            request_id="run:1",
            amount=Decimal("4"),
            charged=Decimal("2"),
            released=Decimal("0"),
            status="active",
        )
        self.added: list[object] = []

    async def get(self, model, pk):
        return None

    async def scalar(self, stmt):
        entity = stmt.column_descriptions[0].get("entity")
        if entity is Wallet:
            return self.wallet
        if entity is BillingReservation:
            return self.reservation
        return None

    def add(self, obj) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        return None


@pytest.mark.asyncio
async def test_charge_reservation_clips_to_remaining() -> None:
    db = ChargeFakeDB()
    user = SimpleNamespace(id=1)
    await BillingService(db).charge_reservation(
        user,
        "run:1",
        Decimal("10"),
        "charge:run:1:node",
        workflow_run_id=db.reservation.workflow_run_id,
        units=10,
        details={"provider": "deepseek", "model": "flash"},
    )
    assert db.wallet.balance == Decimal("8")
    assert db.wallet.reserved == Decimal("2")
    assert db.reservation.charged == Decimal("4")
    ledger = next(item for item in db.added if isinstance(item, WalletLedger))
    assert ledger.amount == Decimal("-2")
    assert ledger.metadata_["capped"] is True


@pytest.mark.asyncio
async def test_charge_reservation_skips_zero_cost_nodes() -> None:
    db = ChargeFakeDB()
    wallet = await BillingService(db).charge_reservation(
        SimpleNamespace(id=1),
        "run:1",
        Decimal("0"),
        "charge:run:1:telegram",
        workflow_run_id=db.reservation.workflow_run_id,
        details={"provider": "telegram", "model": "send"},
    )
    assert wallet.balance == Decimal("10")
    assert wallet.reserved == Decimal("4")
    assert db.reservation.charged == Decimal("2")
    assert not any(isinstance(item, WalletLedger) for item in db.added)


@pytest.mark.asyncio
async def test_charge_reservation_rejects_exhausted_reserve() -> None:
    db = ChargeFakeDB()
    db.reservation.charged = Decimal("4")
    db.wallet.reserved = Decimal("0")
    with pytest.raises(HTTPException) as error:
        await BillingService(db).charge_reservation(
            SimpleNamespace(id=1),
            "run:1",
            Decimal("1"),
            "charge:run:1:node",
            workflow_run_id=db.reservation.workflow_run_id,
        )
    assert error.value.status_code == 409
