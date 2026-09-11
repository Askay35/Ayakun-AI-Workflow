from fastapi import APIRouter, Depends, Header, HTTPException

from services.telegram import TelegramService
from schemas.common import ApiResponse, TelegramWebhookRequest
from deps.services import get_telegram_service
from core.config import settings

router = APIRouter()

@router.post("/webhook")
async def webhook(
    data: TelegramWebhookRequest,
    telegramService: TelegramService = Depends(get_telegram_service),
    secret: str | None = Header(None, alias="X-Telegram-Bot-Api-Secret-Token"),
):
    if settings.telegram_webhook_secret and secret != settings.telegram_webhook_secret:
        raise HTTPException(403, "Неверный webhook secret")
    await telegramService.processUpdate(data)
    return ApiResponse(success=True)