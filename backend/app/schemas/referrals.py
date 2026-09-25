import datetime

from pydantic import BaseModel, Field


class ReferralClaim(BaseModel):
    code: str = Field(min_length=1, max_length=32)


class ReferralItem(BaseModel):
    name: str
    joined_at: datetime.datetime
    purchases: int = 0
    earned: float = 0


class ReferralReward(BaseModel):
    amount: float
    role: str
    referee_name: str | None = None
    plan_name: str | None = None
    created_at: datetime.datetime


class ReferralSummary(BaseModel):
    code: str
    bonus: float
    invited: int
    paying: int
    earned: float
    referred: bool = False
    referrals: list[ReferralItem] = Field(default_factory=list)
    rewards: list[ReferralReward] = Field(default_factory=list)
