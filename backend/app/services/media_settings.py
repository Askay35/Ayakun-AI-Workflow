"""Цены медиа-узлов и провайдер распознавания. Значения правятся в админке."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

VISION_PROVIDERS = frozenset({"deepseek", "gigachat"})
DEFAULT_VISION_PROVIDER = "deepseek"
DEFAULT_VISION_PROMPT = "Что изображено на картинке?"
IMAGE_MAX_BYTES = 30 * 1024 * 1024

DEFAULT_IMAGE_GENERATION_CREDITS = Decimal("50")
DEFAULT_RECOGNITION_DEEPSEEK = Decimal("25")
DEFAULT_RECOGNITION_GIGACHAT = Decimal("40")

MEDIA_CREDIT_KEYS = frozenset({
    "image_generation_credits",
    "image_recognition_credits_deepseek",
    "image_recognition_credits_gigachat",
    "audio_minute_credits",
})


def default_audio_minute_credits() -> Decimal:
    from services.pricing import AUDIO_MINUTE_RUB, credits_for_rubles, quantize_credits

    return quantize_credits(credits_for_rubles(AUDIO_MINUTE_RUB))


def _quantize(amount: Decimal) -> Decimal:
    from services.pricing import quantize_credits

    return quantize_credits(amount)


def _decimal(raw: object, default: Decimal) -> Decimal:
    try:
        amount = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return default
    if amount < 0:
        return default
    return _quantize(amount)


async def _read(pricing: object | None, key: str, default: Decimal | str):
    db = getattr(pricing, "db", None)
    if pricing is None or db is None or not hasattr(pricing, "setting"):
        return default
    stored = await pricing.setting(key, default)
    return default if stored is None else stored


async def vision_provider_name(pricing: object | None) -> str:
    raw = await _read(pricing, "vision_provider", DEFAULT_VISION_PROVIDER)
    name = str(raw or "").strip().lower()
    return name if name in VISION_PROVIDERS else DEFAULT_VISION_PROVIDER


async def image_generation_charge(pricing: object | None) -> Decimal:
    raw = await _read(pricing, "image_generation_credits", DEFAULT_IMAGE_GENERATION_CREDITS)
    return _decimal(raw, DEFAULT_IMAGE_GENERATION_CREDITS)


async def recognition_charge(pricing: object | None) -> tuple[Decimal, str]:
    provider = await vision_provider_name(pricing)
    if provider == "gigachat":
        raw = await _read(pricing, "image_recognition_credits_gigachat", DEFAULT_RECOGNITION_GIGACHAT)
        return _decimal(raw, DEFAULT_RECOGNITION_GIGACHAT), provider
    raw = await _read(pricing, "image_recognition_credits_deepseek", DEFAULT_RECOGNITION_DEEPSEEK)
    return _decimal(raw, DEFAULT_RECOGNITION_DEEPSEEK), provider


async def audio_minute_charge(pricing: object | None) -> Decimal:
    default = default_audio_minute_credits()
    raw = await _read(pricing, "audio_minute_credits", default)
    return _decimal(raw, default)


def normalize_runtime_value(key: str, value: object) -> object:
    if key == "vision_provider":
        name = str(value or "").strip().lower()
        if name not in VISION_PROVIDERS:
            raise ValueError("Провайдер распознавания: deepseek или gigachat")
        return name
    if key in MEDIA_CREDIT_KEYS:
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError("Цена должна быть числом") from exc
        if amount < 0:
            raise ValueError("Цена не может быть отрицательной")
        quantized = _quantize(amount)
        return int(quantized) if quantized == quantized.to_integral_value() else float(quantized)
    return value
