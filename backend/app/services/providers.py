"""Внешние провайдеры: LLM, поиск, Telegram, почта, YooKassa.

Какой провайдер/модель для search / simple / complex — из Settings (админ через .env).
"""

import asyncio
import smtplib

from email.message import EmailMessage
from enum import Enum
from typing import Any, Protocol
import uuid

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field

from openai import OpenAI

from yookassa import Configuration, Payment as YooKassaPayment
from yookassa.domain.exceptions import BadRequestError
from yookassa.payment import PaymentResponse

from schemas.billing import PaymentEvent
from models.billing import Payment, PaymentStatus
from schemas.common import SearchPeriod
from core.config import LLMProviderId, Settings, WebSearchProviderId, settings


class LLMUsage(BaseModel):
    input_tokens: int = 0
    input_cache_hit_tokens: int = 0
    input_cache_miss_tokens: int = 0
    output_tokens: int = 0


class LLMResult(BaseModel):
    text: str
    usage: LLMUsage = Field(default_factory=LLMUsage)
    provider: str = "deepseek"
    model: str
    truncated: bool = False


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    date: str | None = None

class WebSearchProvider(Protocol):
    async def search(self, query: str, period: SearchPeriod | None = None) -> list[SearchResult]: ...


class PaymentProvider(Protocol):
    name: str
    async def create_payment(
        self,
        amount: str,
        currency: str,
        description: str | None = None,
        *,
        idempotency_key: str | uuid.UUID | None = None,
        customer_email: str | None = None,
    ) -> Any: ...
    async def process_payment_webhook(self, payload: dict) -> tuple[str, PaymentStatus]: ...


class NotificationProvider(Protocol):
    async def send(self, destination: str, text: str) -> None: ...


class EmailProvider(Protocol):
    async def send(self, recipient: str, subject: str, text: str) -> None: ...


class SMTPEmailProvider:
    def __init__(self, config: Settings = settings):
        self.config = config

    async def send(self, recipient: str, subject: str, text: str) -> None:
        if not self.config.smtp_host or not self.config.smtp_from_email:
            raise HTTPException(503, "Email provider не настроен")
        message = EmailMessage()
        message["From"] = self.config.smtp_from_email
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(text)

        def deliver() -> None:
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port, timeout=30) as smtp:
                if self.config.smtp_starttls:
                    smtp.starttls()
                if self.config.smtp_username:
                    smtp.login(self.config.smtp_username, self.config.smtp_password or "")
                smtp.send_message(message)

        await asyncio.to_thread(deliver)

def llm_instructions(instructions: str | None = None, output_format: str | None = None) -> str | None:
    parts: list[str] = []
    if instructions and str(instructions).strip():
        parts.append(str(instructions).strip())
    if output_format and str(output_format).strip():
        parts.append(
            "Верни результат в следующем формате:\n"
            f"{str(output_format).strip()}\n\n"
            "Строго соблюдай указанную структуру ответа.\n"
            "Не добавляй дополнительный текст, markdown или пояснения вне этого формата."
        )
    return "\n\n".join(parts) or None


def prompt_input(prompt: str, input_data: str | list[str] | None = None) -> str:
    chunks = [item for item in input_data if item] if isinstance(input_data, list) else (
        [input_data] if input_data else []
    )
    if not chunks:
        return prompt
    return f"{prompt}\n\n" + "\n\n".join(chunks)


def llm_usage_from_api(usage: object | None) -> LLMUsage:
    if usage is None:
        return LLMUsage()
    input_tokens = int(getattr(usage, "input_tokens", 0) or getattr(usage, "prompt_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0) or 0)
    details = getattr(usage, "input_tokens_details", None) or getattr(usage, "prompt_tokens_details", None)
    cache_hit = int(
        getattr(usage, "prompt_cache_hit_tokens", 0)
        or (getattr(details, "cached_tokens", 0) if details is not None else 0)
        or 0
    )
    cache_miss = int(
        getattr(usage, "prompt_cache_miss_tokens", 0)
        or max(input_tokens - cache_hit, 0)
    )
    return LLMUsage(
        input_tokens=input_tokens,
        input_cache_hit_tokens=cache_hit,
        input_cache_miss_tokens=cache_miss,
        output_tokens=output_tokens,
    )


def response_text(response: object) -> str:
    text = getattr(response, "output_text", None)
    if isinstance(text, str) and text:
        return text
    choices = getattr(response, "choices", None) or []
    if choices:
        message = getattr(choices[0], "message", None)
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
    return ""


def response_truncated(response: object) -> bool:
    if getattr(response, "status", None) == "incomplete":
        return True
    incomplete = getattr(response, "incomplete_details", None)
    if getattr(incomplete, "reason", None) in {"max_output_tokens", "length"}:
        return True
    choices = getattr(response, "choices", None) or []
    if choices:
        return getattr(choices[0], "finish_reason", None) == "length"
    return False


class LLMProvider(Protocol):
    async def prompt(
        self,
        prompt: str,
        instructions: str | None = None,
        input_data: str | list[str] | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        output_format: str | None = None,
    ) -> LLMResult: ...

class OpenAICompatibleProvider:
    """Клиент OpenAI-compatible Responses API (DeepSeek)."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        timeout: float = 30,
        retries: int = 0,
    ):
        self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
   
    async def prompt(
        self,
        prompt: str,
        instructions: str | None = None,
        input_data: str | list[str] | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        output_format: str | None = None,
    ) -> LLMResult:
        selected_model = model or self.model
        payload: dict[str, object] = {
            "model": selected_model,
            "input": prompt_input(prompt, input_data),
        }
        combined_instructions = llm_instructions(instructions, output_format)
        if combined_instructions:
            payload["instructions"] = combined_instructions
        if max_tokens is not None:
            payload["max_output_tokens"] = max_tokens

        def create():
            return self.client.responses.create(**payload)

        response = await asyncio.to_thread(create)
        return LLMResult(
            text=response_text(response),
            model=selected_model,
            truncated=response_truncated(response),
            usage=llm_usage_from_api(getattr(response, "usage", None)),
        )


class DeepSeekProvider(OpenAICompatibleProvider):
    def __init__(self, config: Settings = settings):
        if not config.deepseek_api_key:
            raise HTTPException(503, "DeepSeek не настроен")
        super().__init__(
            model=config.deepseek_simple_model,
            api_key=config.deepseek_api_key,
            base_url=config.deepseek_base_url,
            timeout=config.llm_timeout_seconds,
            retries=0,
        )


def build_llm_providers(config: Settings = settings) -> dict[str, LLMProvider]:
    """Реестр LLM: ключ = LLMProviderId.value. Сюда добавлять новых провайдеров."""
    return {
        LLMProviderId.deepseek.value: DeepSeekProvider(config),
        # LLMProviderId.qwen.value: QwenProvider(config),
    }


def build_web_search_providers(
    client: httpx.AsyncClient,
    config: Settings = settings,
) -> dict[str, WebSearchProvider]:
    """Реестр web search: ключ = WebSearchProviderId.value."""
    return {
        WebSearchProviderId.serper.value: SerperWebSearchProvider(client, config),
    }


def _provider_key(name: str | LLMProviderId | WebSearchProviderId) -> str:
    return name.value if isinstance(name, Enum) else name


class ModelRouter:
    """Выбор провайдера и модели по типу операции (simple_text / complex_text)."""

    def __init__(
        self,
        config: Settings = settings,
        providers: dict[str, LLMProvider] | None = None,
    ):
        self.config = config
        self.providers = providers if providers is not None else build_llm_providers(config)

    def _default_model(self, provider_name: str, operation: str) -> str:
        return self.config.llm_model_for(provider_name, operation)

    def select(
        self,
        requested: str | LLMProviderId | None = None,
        *,
        operation: str = "simple_text",
    ) -> tuple[LLMProvider, str]:
        if operation == "complex_text":
            name = requested or self.config.complex_llm_provider
        else:
            name = requested or self.config.simple_llm_provider
        key = _provider_key(name)
        provider = self.providers.get(key)
        if not provider:
            raise HTTPException(422, f"Неизвестный LLM provider: {key}")
        return provider, self._default_model(key, operation)

    def validate_model(self, model: str) -> str:
        allowed = {item.strip() for item in self.config.allowed_llm_models.split(",") if item.strip()}
        if allowed and model not in allowed:
            raise HTTPException(422, f"Модель не разрешена: {model}")
        return model


class WebSearchRouter:
    def __init__(
        self,
        client: httpx.AsyncClient,
        config: Settings = settings,
        providers: dict[str, WebSearchProvider] | None = None,
    ):
        self.config = config
        self.providers = (
            providers if providers is not None else build_web_search_providers(client, config)
        )

    def select(self, requested: str | WebSearchProviderId | None = None) -> WebSearchProvider:
        name = requested or self.config.web_search_provider
        key = _provider_key(name)
        provider = self.providers.get(key)
        if not provider:
            raise HTTPException(422, f"Неизвестный web search provider: {key}")
        return provider


class SerperWebSearchProvider:
    def __init__(self, client: httpx.AsyncClient, config: Settings = settings):
        self.client = client
        self.config = config

    async def search(self, query: str, period: SearchPeriod | None = None) -> list[SearchResult]:
        if not self.config.serper_key:
            raise HTTPException(503, "Serper key не настроен")
        
        search_params = {
            "q": query,
            "gl": "ru",
            "hl": "ru",
        }
        if period:
            search_params["tbs"] = f"qdr:{period.value}"

        response = await self.client.post(
            "https://google.serper.dev/search",
            json=search_params,
            headers={"X-API-KEY": self.config.serper_key, "Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
        if not data["organic"]:
            raise HTTPException(500, "Ошибка web search (Serper) API: поле результатов не найдено")
        return [SearchResult(title=item["title"], url=item["link"], snippet=item["snippet"], date=item.get("date")) for item in data["organic"]]


class TelegramNotificationProvider:
    def __init__(self, client: httpx.AsyncClient, config: Settings = settings):
        self.client = client
        self.config = config

    async def send(self, destination: str, text: str) -> None:
        if not self.config.telegram_bot_token:
            raise HTTPException(503, "Telegram bot не настроен")
        response = await self.client.post(
            f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage",
            json={"chat_id": destination, "text": text, "parse_mode": "MarkdownV2"},
            timeout=self.config.provider_timeout_seconds,
        )
        response.raise_for_status()


class YooKassaProvider:
    name = "yookassa"
    request_timeout_seconds = 20

    def __init__(self, client: httpx.AsyncClient, config: Settings = settings):
        self.client = client
        self.config = config

    def _configure(self) -> None:
        if not self.config.yookassa_account_id or not self.config.yookassa_secret_key:
            raise HTTPException(503, "Платежный провайдер не настроен")
        Configuration.account_id = self.config.yookassa_account_id
        Configuration.secret_key = self.config.yookassa_secret_key
        Configuration.timeout = self.request_timeout_seconds
        Configuration.max_attempts = 1

    async def create_payment(
        self,
        amount: str,
        currency: str,
        description: str | None = None,
        *,
        idempotency_key: str | uuid.UUID | None = None,
        customer_email: str | None = None,
    ) -> PaymentResponse:
        self._configure()
        if not customer_email:
            raise HTTPException(400, "Для оплаты нужен email (чек 54-ФЗ)")
        description = description or "Оплата тарифа Ayakun"
        payload = {
            "amount": {
                "value": amount,
                "currency": currency
            },
            "confirmation": {
                "type": "redirect",
                "return_url": self.config.yookassa_return_url
            },
            "capture": True,
            "description": description,
            "receipt": {
                "customer": {"email": customer_email},
                "items": [
                    {
                        "description": description[:128],
                        "quantity": "1.00",
                        "amount": {"value": amount, "currency": currency},
                        "vat_code": 1,
                        "payment_mode": "full_payment",
                        "payment_subject": "service",
                    }
                ],
            },
        }
        key = str(idempotency_key) if idempotency_key else str(uuid.uuid4())
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(YooKassaPayment.create, payload, key),
                timeout=self.request_timeout_seconds + 5,
            )
        except TimeoutError as exc:
            raise HTTPException(504, "ЮKassa не ответила вовремя") from exc
        except BadRequestError as exc:
            detail = None
            if getattr(exc, "content", None):
                detail = exc.content.get("description") or exc.content.get("parameter")
            raise HTTPException(400, detail or "Некорректный запрос к ЮKassa") from exc

    async def process_payment_webhook(self, payload: dict) -> tuple[str, PaymentStatus]:
        payment = payload.get("object")
        event = payload.get("event")
        if not event or event not in PaymentEvent or not isinstance(payment, dict) or not payment.get("id") or not payment.get("status") in PaymentStatus._value2member_map_:
            raise HTTPException(400, "Некорректный webhook payload")
        return payment["id"], PaymentStatus(payment["status"])
