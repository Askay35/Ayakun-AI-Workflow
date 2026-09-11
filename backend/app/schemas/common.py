from enum import Enum
from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiError(BaseModel):
    code: str
    message: str


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: T | None = None
    error: ApiError | None = None

class TelegramWebhookChatField(BaseModel):
    id: int
    first_name: str
    username: str | None = None
    type: str

class TelegramWebhookMessageField(BaseModel):
    chat: TelegramWebhookChatField
    text:str

class TelegramWebhookRequest(BaseModel):
    message: TelegramWebhookMessageField


class SearchPeriod(str, Enum):
    HOUR = "h"
    DAY = "d"
    WEEK = "w"
    MONTH = "m"
    YEAR = "y"

