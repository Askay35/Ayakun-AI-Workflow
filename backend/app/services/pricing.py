"""Конфигурируемые тарифы провайдеров и расчёты стоимости в credits."""

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from math import floor

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.billing import PricingRate, RuntimeSetting
from schemas.workflow import WorkflowGraph
from services.providers import llm_instructions
from utils.deepseek_tokenizer import count_prompt_tokens

THOUSAND = Decimal("1000")
CREDIT_PROVIDER_COST_USD = Decimal("0.001")
CREDIT_SALE_PRICE_USD = Decimal("0.002")
# DeepSeek peak = 2× off-peak. Ставки credits берём по peak, чтобы
# продажа credit за $0.002 давала 50% gross даже в пиковые часы.
MARGIN_MULTIPLIER = Decimal("2")
# Типичный объём выдачи Serper, который потом уходит во вход prompt.
ESTIMATED_SEARCH_CONTEXT_TOKENS = 800
# Типичный ответ предыдущего prompt-узла во входе следующего.
ESTIMATED_PROMPT_CONTEXT_TOKENS = 400


@dataclass(frozen=True)
class Price:
    provider: str
    model: str
    input_cache_hit: Decimal
    input_cache_miss: Decimal
    output: Decimal
    search: Decimal = Decimal("0")


DEFAULT_PRICES: dict[tuple[str, str], Price] = {
    ("deepseek", "deepseek-v4-flash"): Price(
        "deepseek", "deepseek-v4-flash", Decimal("0.014"), Decimal("0.44"), Decimal("1.32")
    ),
    ("deepseek", "deepseek-v4-pro"): Price(
        "deepseek", "deepseek-v4-pro", Decimal("0.044"), Decimal("1.32"), Decimal("3.96")
    ),
    ("serper", "search"): Price(
        "serper", "search", Decimal("0"), Decimal("0"), Decimal("0"), Decimal("1")
    ),
}


def usage_credits(price: Price, cache_hit: int, cache_miss: int, output: int) -> Decimal:
    return (
        Decimal(cache_hit) * price.input_cache_hit
        + Decimal(cache_miss) * price.input_cache_miss
        + Decimal(output) * price.output
    ) / THOUSAND


CREDIT_QUANTUM = Decimal("0.000001")


def quantize_credits(amount: Decimal) -> Decimal:
    """Фактическое списание по usage: без округления до целого кредита."""
    if amount <= 0:
        return Decimal("0")
    return Decimal(amount).quantize(CREDIT_QUANTUM)


def billable_credits(amount: Decimal) -> Decimal:
    """Оценка запуска: целое число credits, округление вверх."""
    if amount <= 0:
        return Decimal("0")
    return Decimal(amount).to_integral_value(rounding=ROUND_CEILING)


def provider_cost_usd(credits: Decimal) -> Decimal:
    """Оценка себестоимости: списание уже с 50% margin, поэтому COGS = credits × $0.001."""
    return credits * CREDIT_PROVIDER_COST_USD


def maximum_output_tokens(price: Price, budget: Decimal, input_tokens: int) -> int:
    input_cost = usage_credits(price, 0, input_tokens, 0)
    if budget <= input_cost or price.output <= 0:
        return 0
    return max(0, floor((budget - input_cost) * THOUSAND / price.output))


class PricingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, provider: str, model: str) -> Price:
        row = await self.db.scalar(
            select(PricingRate).where(
                PricingRate.provider == provider,
                PricingRate.model == model,
                PricingRate.active.is_(True),
            )
        )
        if row:
            return Price(
                row.provider,
                row.model,
                row.input_cache_hit_credits_per_1k,
                row.input_cache_miss_credits_per_1k,
                row.output_credits_per_1k,
                row.search_credits,
            )
        fallback = DEFAULT_PRICES.get((provider, model))
        if not fallback:
            raise ValueError(f"Тариф для {provider}/{model} не настроен")
        return fallback

    async def setting(self, key: str, default=None):
        row = await self.db.get(RuntimeSetting, key)
        return row.value if row is not None else default

    async def estimate_graph(self, graph: WorkflowGraph) -> Decimal:
        total = Decimal("0")
        for node in graph.nodes:
            node_type = _node_type(node)
            if node_type == "web_search":
                total += billable_credits((await self.get("serper", "search")).search)
            elif node_type == "prompt":
                model = node.model or (
                    "deepseek-v4-pro" if node.complexity == "complex_text" else "deepseek-v4-flash"
                )
                price = await self.get("deepseek", model)
                total += billable_credits(usage_credits(price, 0, _estimated_prompt_input_tokens(node, graph), 0))
        return total


def _node_type(node: object) -> str:
    value = getattr(node, "type", "")
    return value.value if hasattr(value, "value") else str(value)


def _estimated_prompt_input_tokens(node: object, graph: WorkflowGraph | None = None) -> int:
    tokens = count_prompt_tokens(
        getattr(node, "prompt", "") or "",
        instructions=llm_instructions(
            getattr(node, "instructions", None),
            getattr(node, "output_format", None),
        ),
    )
    if graph is None:
        return tokens
    by_id = {item.id: item for item in graph.nodes}
    for parent_id in getattr(node, "parents", []) or []:
        parent = by_id.get(parent_id)
        if parent is None:
            continue
        parent_type = _node_type(parent)
        if parent_type == "web_search":
            tokens += ESTIMATED_SEARCH_CONTEXT_TOKENS
        elif parent_type in {"prompt", "http_request"}:
            tokens += ESTIMATED_PROMPT_CONTEXT_TOKENS
    return tokens


def node_estimate(node: object, graph: WorkflowGraph | None = None) -> Decimal:
    node_type = _node_type(node)
    if node_type == "web_search":
        return billable_credits(DEFAULT_PRICES[("serper", "search")].search)
    if node_type in {"telegram_send", "http_request"}:
        return Decimal("0")
    if node_type != "prompt":
        return Decimal("0")
    complexity = getattr(node, "complexity", "simple_text")
    model = getattr(node, "model", None) or (
        "deepseek-v4-pro" if complexity == "complex_text" else "deepseek-v4-flash"
    )
    price = DEFAULT_PRICES[("deepseek", model)]
    return billable_credits(usage_credits(price, 0, _estimated_prompt_input_tokens(node, graph), 0))


def estimate_run_cost(graph: WorkflowGraph | dict | None) -> Decimal:
    """Приблизительная стоимость; фактическое списание всегда строится по usage."""
    if graph is None:
        return Decimal("0")
    if isinstance(graph, dict):
        graph = WorkflowGraph.model_validate(graph)
    return sum((node_estimate(node, graph) for node in graph.nodes), Decimal("0"))
