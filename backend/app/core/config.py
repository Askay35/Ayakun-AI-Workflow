import secrets
from decimal import Decimal
from enum import Enum

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProviderId(str, Enum):
    """Известные LLM-провайдеры. Значения = ключи реестра и SIMPLE/COMPLEX_LLM_PROVIDER."""

    deepseek = "deepseek"
    qwen = "qwen"


class WebSearchProviderId(str, Enum):
    """Известные провайдеры веб-поиска. Значение = WEB_SEARCH_PROVIDER."""

    serper = "serper"


class Settings(BaseSettings):
    environment: str = "development"
    db_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ayakun"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    celery_result_backend: str = "redis://localhost:6379/1"

    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 30
    token_expiration_time: int = 60
    login_code_expiration_time: int = 5

    serper_key: str | None = None
    langsearch_key: str | None = None

    telegram_bot_token: str | None = None
    telegram_webhook_secret: str | None = None
    frontend_url: str = "http://localhost:3000"
    debug: bool = False
    admin_login: str | None = None
    admin_password: str | None = None

    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str | None = None
    smtp_starttls: bool = True

    dashscope_api_key: str | None = None
    dashscope_base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    qwen_search_model: str = "qwen-turbo"
    qwen_simple_model: str = "qwen-turbo"
    qwen_complex_model: str = "qwen-plus"
    gigachat_auth_key: str | None = None
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_complex_model: str = "deepseek-v4-pro"
    deepseek_simple_model: str = "deepseek-flash"
    deepseek_vision_model: str = "deepseek-v4-flash-vision-exp"
    # Admin routing: which provider/model for each workflow stage
    web_search_provider: WebSearchProviderId = WebSearchProviderId.serper
    simple_llm_provider: LLMProviderId = LLMProviderId.deepseek
    simple_llm_model: str | None = None
    complex_llm_provider: LLMProviderId = LLMProviderId.deepseek
    complex_llm_model: str | None = None
    allowed_llm_models: str = "deepseek-flash,deepseek-v4-flash,deepseek-v4-pro,qwen-turbo,qwen-plus"
    provider_timeout_seconds: float = 60
    provider_max_retries: int = 3
    llm_timeout_seconds: float = 180
    llm_max_retries: int = 3
    llm_max_output_tokens: int = 8192
    initial_token_balance: Decimal = Decimal("100")
    default_run_cap_credits: Decimal = Decimal("100")
    max_workflows_count: int = 300
    # Типы узлов, которые нельзя запускать отдельно от цепочки (через запятую).
    solo_run_blocked_node_types: str = "if_else"
   

    yookassa_account_id: str | None = None
    yookassa_secret_key: str | None = None
    yookassa_return_url: str = "http://localhost:3000/billing"
   
    credits_cost_multiplier: Decimal = Decimal("2")
    cost_prompt_simple: Decimal = Decimal("100")
    cost_prompt_complex: Decimal = Decimal("300")
    cost_web_search: Decimal = Decimal("150")
    cost_telegram_send: Decimal = Decimal("5")
    reserve_tokens_per_node: Decimal = Decimal("100")
    llm_tokens_per_1000: Decimal = Decimal("40")
    web_search_tokens: Decimal = Decimal("150")
    telegram_send_tokens: Decimal = Decimal("5")
    payment_tokens_per_ruble: Decimal = Decimal("100")
    payment_credits_per_usd: Decimal = Decimal("500")


    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    def llm_model_for(self, provider: str | LLMProviderId, operation: str) -> str:
        """Модель для провайдера и операции; overrides SIMPLE/COMPLEX_LLM_MODEL имеют приоритет."""
        key = provider.value if isinstance(provider, LLMProviderId) else provider
        if operation == "complex_text":
            if self.complex_llm_model:
                return self.complex_llm_model
            by_provider = {
                LLMProviderId.deepseek.value: self.deepseek_complex_model,
                LLMProviderId.qwen.value: self.qwen_complex_model,
            }
        else:
            if self.simple_llm_model:
                return self.simple_llm_model
            by_provider = {
                LLMProviderId.deepseek.value: self.deepseek_simple_model,
                LLMProviderId.qwen.value: self.qwen_simple_model,
            }
        if key not in by_provider:
            raise ValueError(f"Неизвестный LLM provider: {key}")
        return by_provider[key]

    def solo_run_blocked_types(self) -> frozenset[str]:
        return frozenset(
            item.strip()
            for item in self.solo_run_blocked_node_types.split(",")
            if item.strip()
        )

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.environment == "production" and "secret_key" not in self.model_fields_set:
            raise ValueError("SECRET_KEY обязателен в production")
        if self.environment == "production" and (
            len(self.secret_key) < 32 or self.secret_key.startswith("change-me")
        ):
            raise ValueError("SECRET_KEY должен быть случайным и содержать минимум 32 символа")
        return self

settings = Settings()