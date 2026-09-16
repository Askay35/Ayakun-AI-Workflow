from pydantic import BaseModel, ConfigDict, Field

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

    model_config = ConfigDict(from_attributes=True)