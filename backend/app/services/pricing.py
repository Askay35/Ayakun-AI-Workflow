"""Конфигурируемые тарифы провайдеров и расчёты стоимости в credits."""

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from math import ceil, floor

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
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
DEFAULT_MAX_OUTPUT_TOKENS = 8_000
INPUT_TOKEN_PADDING = 32
INPUT_TOKEN_SAFETY_RATIO = Decimal("0.15")


@dataclass(frozen=True)
class Price:
    provider: str
    model: str
    input_cache_hit: Decimal
    input_cache_miss: Decimal
    output: Decimal
    search: Decimal = Decimal("0")


_FLASH_PRICE = Price(
    "deepseek", "deepseek-flash", Decimal("0.014"), Decimal("0.44"), Decimal("1.32")
)
DEFAULT_PRICES: dict[tuple[str, str], Price] = {
    ("deepseek", "deepseek-flash"): _FLASH_PRICE,
    ("deepseek", "deepseek-v4-flash"): _FLASH_PRICE,
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


def billed_credits(price: Price, cache_hit: int, cache_miss: int, output: int) -> Decimal:
    """Списание LLM: usage × credits_cost_multiplier, квантование как у фактического charge."""
    return quantize_credits(
        usage_credits(price, cache_hit, cache_miss, output) * settings.credits_cost_multiplier
    )


def billable_credits(amount: Decimal) -> Decimal:
    """Оценка запуска: целое число credits, округление вверх."""
    if amount <= 0:
        return Decimal("0")
    return Decimal(amount).to_integral_value(rounding=ROUND_CEILING)


# Пакет 2000 credits = 390 RUB → 1 credit = 0.195 RUB.
CREDIT_PACK_RUB = Decimal("390")
CREDIT_PACK_SIZE = Decimal("2000")
RUB_PER_CREDIT = CREDIT_PACK_RUB / CREDIT_PACK_SIZE
IMAGE_MEDIA_CREDITS = Decimal("50")
AUDIO_MINUTE_RUB = Decimal("0.5")


def credits_for_rubles(rubles: Decimal) -> Decimal:
    return Decimal(rubles) / RUB_PER_CREDIT


def image_generation_credits() -> Decimal:
    return IMAGE_MEDIA_CREDITS


def image_recognition_credits() -> Decimal:
    return IMAGE_MEDIA_CREDITS


def audio_transcription_credits(minutes: int) -> Decimal:
    safe = max(1, int(minutes))
    return quantize_credits(credits_for_rubles(AUDIO_MINUTE_RUB * safe))


def media_estimate_credits(node_type: str) -> Decimal:
    if node_type in {"image_generation", "image_recognition"}:
        return IMAGE_MEDIA_CREDITS
    if node_type == "audio_transcription":
        return billable_credits(credits_for_rubles(AUDIO_MINUTE_RUB))
    return Decimal("0")


def provider_cost_usd(credits: Decimal) -> Decimal:
    """Оценка себестоимости: списание уже с 50% margin, поэтому COGS = credits × $0.001."""
    return credits * CREDIT_PROVIDER_COST_USD


def padded_input_tokens(tokens: int) -> int:
    """Запас на расхождение локального tokenizer с usage API."""
    if tokens <= 0:
        return 0
    extra = max(INPUT_TOKEN_PADDING, ceil(tokens * float(INPUT_TOKEN_SAFETY_RATIO)))
    return tokens + extra


def maximum_output_tokens(price: Price, budget: Decimal, input_tokens: int) -> int:
    if price.output <= 0:
        return 0
    if billed_credits(price, 0, input_tokens, 0) >= budget:
        return 0
    multiplier = settings.credits_cost_multiplier
    input_raw = usage_credits(price, 0, input_tokens, 0)
    output = floor((budget / multiplier - input_raw) * THOUSAND / price.output)
    while output > 0 and billed_credits(price, 0, input_tokens, output) > budget:
        output -= 1
    return max(0, output)


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
                price = await self.get("deepseek", _prompt_model(node))
                total += _prompt_estimate_credits(price, node, graph)
            else:
                total += media_estimate_credits(node_type)
        return total


def _node_type(node: object) -> str:
    value = getattr(node, "type", "")
    return value.value if hasattr(value, "value") else str(value)


def _prompt_model(node: object) -> str:
    complexity = getattr(node, "complexity", "simple_text")
    return getattr(node, "model", None) or (
        "deepseek-v4-pro" if complexity == "complex_text" else "deepseek-flash"
    )


def _prompt_max_output_tokens(node: object) -> int:
    raw = getattr(node, "max_output_tokens", None)
    try:
        tokens = int(raw) if raw is not None else DEFAULT_MAX_OUTPUT_TOKENS
    except (TypeError, ValueError):
        tokens = DEFAULT_MAX_OUTPUT_TOKENS
    return max(1, tokens)


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


def _prompt_estimate_credits(price: Price, node: object, graph: WorkflowGraph | None = None) -> Decimal:
    return billable_credits(
        billed_credits(
            price,
            0,
            _estimated_prompt_input_tokens(node, graph),
            _prompt_max_output_tokens(node),
        )
    )


def node_estimate(node: object, graph: WorkflowGraph | None = None) -> Decimal:
    node_type = _node_type(node)
    if node_type == "web_search":
        return billable_credits(DEFAULT_PRICES[("serper", "search")].search)
    if node_type in {"telegram_send", "http_request"}:
        return Decimal("0")
    media = media_estimate_credits(node_type)
    if media:
        return media
    if node_type != "prompt":
        return Decimal("0")
    price = DEFAULT_PRICES[("deepseek", _prompt_model(node))]
    return _prompt_estimate_credits(price, node, graph)


def estimate_run_cost(graph: WorkflowGraph | dict | None) -> Decimal:
    """Максимальная стоимость запуска при полном лимите ответа; списание — по usage."""
    if graph is None:
        return Decimal("0")
    if isinstance(graph, dict):
        graph = WorkflowGraph.model_validate(graph)
    return sum((node_estimate(node, graph) for node in graph.nodes), Decimal("0"))
