from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from schemas.user import GmailAccountResponse, UserResponse


class EmailRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=120)


class EmailRegisterConfirmRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class EmailLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse
    gmail_account: GmailAccountResponse | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


class PurposeTokenRequest(BaseModel):
    token: str


class ResetRequest(BaseModel):
    email: EmailStr


class ResetConfirmRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class GoogleCodeRequest(BaseModel):
    code: str
    code_verifier: str
    state: str
    redirect_uri: str | None = None


class GoogleAuthorizeRequest(BaseModel):
    code_challenge: str = Field(min_length=43, max_length=128)
    redirect_uri: str | None = None
    purpose: Literal["login", "gmail", "link"] = "login"


class TelegramCodeRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)
