import httpx
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import helper
from services.auth import AuthService
from services.user import UserService
from schemas.common import ApiResponse, TelegramWebhookRequest
import redis.asyncio as redis
from core.config import settings
import logging

logger = logging.getLogger(__name__)

class TelegramService:

    def __init__(self, db: AsyncSession, redis: redis.Redis, userService: UserService, authService: AuthService, http_client: httpx.AsyncClient):
        self.db = db
        self.redis = redis
        self.authService = authService
        self.http_client = http_client
        self.userService = userService

    async def send_message(self, chat_id: int, text: str):
        if not settings.telegram_bot_token:
            raise RuntimeError("Telegram bot is not configured")
        try:
            response = await self.http_client.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "MarkdownV2"
                },
            )
        except httpx.RequestError:
            logger.warning("Telegram login message failed", extra={"event": "telegram.send_failed"})
            raise RuntimeError("Ошибка запроса к telegram") from None
        if response.is_error:
            logger.warning(
                "Telegram login message rejected",
                extra={"event": "telegram.send_failed", "status_code": response.status_code},
            )
            raise RuntimeError("Ошибка запроса к telegram")
        return response.json()

    async def processUpdate(self, data: TelegramWebhookRequest):
        if data.message.text == "/start logincode":
            return await self.sendLoginCode(data)
        else:
            return ApiResponse(success=False, message="Invalid command")

    async def sendLoginCode(self, data: TelegramWebhookRequest):
        rate_key = f"telegram_login_rate:{data.message.chat.id}"
        attempts = await self.redis.incr(rate_key)
        if attempts == 1:
            await self.redis.expire(rate_key, 60)
        if attempts > 5:
            raise HTTPException(429, "Слишком много запросов кода")
        user = await self.userService.get_user_by_chat_id(data.message.chat.id)
        
        if not user:
            await self.authService.telegramRegister(data.message.chat.id, data.message.chat.first_name)
        
        for _ in range(5):
            code = helper.generate_login_code()
            created = await self.redis.set(
                f"telegram_login_code:{helper.hash_token(code)}",
                data.message.chat.id,
                ex=60 * settings.login_code_expiration_time,
                nx=True,
            )
            if created:
                break
        else:
            raise RuntimeError("Не удалось создать уникальный код входа")
        await self.send_message(
            data.message.chat.id,
            (
                "*Ваш код для входа:*\n\n"
                f"`{code}`\n\n"
                "Он действителен в течение 5 минут\\."
            ),
       
        )
       