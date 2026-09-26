import datetime

from pydantic import BaseModel, ConfigDict, Field

from schemas.common import SearchPeriod
from schemas.workflow import ScheduleSlot

class IdentityResponse(BaseModel):
    provider: str
    subject: str
    model_config = ConfigDict(from_attributes=True)


class GmailAccountResponse(BaseModel):
    id: int
    email: str | None = None


class UserResponse(BaseModel):
    id: int
    chat_id: int | None
    name: str
    email: str | None
    identities: list[IdentityResponse] = Field(default_factory=list)
    gmail_accounts: list[GmailAccountResponse] = Field(default_factory=list)
    onboarded_at: datetime.datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class OnboardingComplete(BaseModel):
    """Ответы опроса после регистрации. Без template_slug опрос просто пропускается."""

    answers: dict[str, str] = Field(default_factory=dict, max_length=10)
    template_slug: str | None = Field(default=None, max_length=80)
    schedule_slots: list[ScheduleSlot] = Field(default_factory=list, max_length=5)
    schedule_timezone: str = Field(default="UTC", max_length=64)
    search_period: SearchPeriod | None = None
    mobile: bool = False


class OnboardingResult(BaseModel):
    workflow_id: str | None = None
