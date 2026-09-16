from __future__ import annotations

import asyncio

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import helper
from core.config import settings
from models.user import GoogleOAuthToken, User
from schemas.user import GmailAccountResponse, UserResponse

LOGIN_SCOPES = ("openid", "email", "profile")
GMAIL_SCOPES = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
)
GMAIL_AUTHORIZE_SCOPES = (*LOGIN_SCOPES, *GMAIL_SCOPES)


def gmail_scope_string() -> str:
    return " ".join(GMAIL_AUTHORIZE_SCOPES)


def login_scope_string() -> str:
    return " ".join(LOGIN_SCOPES)


def _account_payload(row: GoogleOAuthToken) -> GmailAccountResponse:
    return GmailAccountResponse(id=row.id, email=row.email)


def refresh_gmail_access_token(refresh_token: str) -> str:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise ValueError("Не удалось авторизоваться в Gmail") from exc
    if not settings.google_client_id or not settings.google_client_secret:
        raise ValueError("Не удалось авторизоваться в Gmail")
    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=list(GMAIL_AUTHORIZE_SCOPES),
    )
    try:
        credentials.refresh(Request())
    except Exception:
        raise ValueError("Не удалось авторизоваться в Gmail") from None
    token = getattr(credentials, "token", None)
    if not token:
        raise ValueError("Не удалось авторизоваться в Gmail")
    return str(token)


async def list_gmail_accounts(db: AsyncSession, user_id: int) -> list[GoogleOAuthToken]:
    result = await db.scalars(
        select(GoogleOAuthToken).where(GoogleOAuthToken.user_id == user_id).order_by(GoogleOAuthToken.id)
    )
    return list(result.all())


async def user_response(db: AsyncSession, user: User) -> UserResponse:
    payload = UserResponse.model_validate(user)
    rows = await list_gmail_accounts(db, user.id)
    return payload.model_copy(update={"gmail_accounts": [_account_payload(row) for row in rows]})


async def save_gmail_grant(
    db: AsyncSession,
    user: User,
    *,
    google_sub: str,
    email: str | None,
    refresh_token: str | None,
    scopes: str,
) -> GoogleOAuthToken:
    existing = await db.scalar(
        select(GoogleOAuthToken).where(
            GoogleOAuthToken.user_id == user.id,
            GoogleOAuthToken.google_sub == google_sub,
        )
    )
    if not refresh_token:
        if existing:
            existing.email = email
            if scopes:
                existing.scopes = scopes
            existing.updated_at = helper.utcnow()
            await db.flush()
            return existing
        raise HTTPException(400, "Не удалось получить доступ к Gmail")
    encrypted = helper.encrypt_secret(refresh_token)
    if existing:
        existing.email = email
        existing.refresh_token_encrypted = encrypted
        existing.scopes = scopes
        existing.updated_at = helper.utcnow()
        await db.flush()
        return existing
    row = GoogleOAuthToken(
        user_id=user.id,
        google_sub=google_sub,
        email=email,
        refresh_token_encrypted=encrypted,
        scopes=scopes,
    )
    db.add(row)
    await db.flush()
    return row


async def access_token_for_account(db: AsyncSession, user_id: int, account_id: int) -> str | None:
    row = await db.scalar(
        select(GoogleOAuthToken).where(
            GoogleOAuthToken.id == account_id,
            GoogleOAuthToken.user_id == user_id,
        )
    )
    if not row:
        return None
    try:
        refresh = helper.decrypt_secret(row.refresh_token_encrypted)
        return await asyncio.to_thread(refresh_gmail_access_token, refresh)
    except Exception:
        raise ValueError("Не удалось авторизоваться в Gmail") from None


async def disconnect_gmail(db: AsyncSession, user: User, account_id: int) -> UserResponse:
    row = await db.scalar(
        select(GoogleOAuthToken).where(
            GoogleOAuthToken.id == account_id,
            GoogleOAuthToken.user_id == user.id,
        )
    )
    if row:
        await db.delete(row)
    await db.commit()
    return await user_response(db, user)
