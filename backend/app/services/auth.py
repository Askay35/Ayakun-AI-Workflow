import asyncio
import datetime
import json
import secrets

import httpx
import redis.asyncio as redis
from fastapi import HTTPException
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token as google_id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import helper
from core.config import settings
from models.user import AuthIdentity, IdentityProvider, RefreshToken, User
from schemas.auth import TokenPair
from services.providers import EmailProvider


class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        redis_client: redis.Redis,
        http_client: httpx.AsyncClient | None = None,
        email_provider: EmailProvider | None = None,
    ):
        self.db = db
        self.redis = redis_client
        self.http_client = http_client
        self.email_provider = email_provider

    async def _tokens(self, user: User) -> TokenPair:
        raw, token_hash = helper.new_refresh_token()
        self.db.add(RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=settings.refresh_token_days),
        ))
        await self.db.commit()
        loaded = await self.db.scalar(
            select(User).options(selectinload(User.identities)).where(User.id == user.id)
        )
        return TokenPair(access_token=helper.generate_token(user.id), refresh_token=raw, user=loaded)

    async def register_email(self, email: str, password: str, name: str) -> TokenPair:
        email = email.lower()
        if await self.db.scalar(select(User).where(User.email == email)):
            raise HTTPException(409, "Email уже используется")
        user = User(name=name, email=email, password_hash=helper.hash_password(password))
        self.db.add(user)
        await self.db.flush()
        self.db.add(AuthIdentity(user_id=user.id, provider=IdentityProvider.email, subject=email))
        verification = helper.create_purpose_token(user.id, "email_verify", 24 * 60)
        await self.redis.set(
            f"purpose:email_verify:{helper.hash_token(verification)}",
            user.id,
            ex=24 * 60 * 60,
        )
        if not self.email_provider:
            raise HTTPException(503, "Email provider не настроен")
        await self.email_provider.send(
            email,
            "Подтверждение email в Ayakun",
            f"{settings.frontend_url}/auth/verify-email?token={verification}",
        )
        return await self._tokens(user)

    async def login_email(self, email: str, password: str) -> TokenPair:
        user = await self.db.scalar(select(User).where(User.email == email.lower()))
        if not user or not user.password_hash or not helper.verify_password(password, user.password_hash):
            raise HTTPException(401, "Неверный email или пароль")
        if not user.is_active:
            raise HTTPException(403, "Пользователь отключен")
        return await self._tokens(user)

    async def refresh(self, raw_token: str) -> TokenPair:
        now = datetime.datetime.now(datetime.UTC)
        token = await self.db.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == helper.hash_token(raw_token)).with_for_update()
        )
        if not token or token.revoked_at or token.expires_at <= now:
            raise HTTPException(401, "Refresh token недействителен")
        new_raw, new_hash = helper.new_refresh_token()
        token.revoked_at = now
        token.replaced_by_hash = new_hash
        self.db.add(RefreshToken(
            user_id=token.user_id,
            token_hash=new_hash,
            expires_at=now + datetime.timedelta(days=settings.refresh_token_days),
        ))
        await self.db.commit()
        user = await self.db.scalar(
            select(User).options(selectinload(User.identities)).where(User.id == token.user_id)
        )
        if not user or not user.is_active:
            raise HTTPException(401, "Refresh token недействителен")
        return TokenPair(access_token=helper.generate_token(user.id), refresh_token=new_raw, user=user)

    async def revoke_refresh(self, raw_token: str) -> None:
        token = await self.db.scalar(select(RefreshToken).where(RefreshToken.token_hash == helper.hash_token(raw_token)))
        if token and not token.revoked_at:
            token.revoked_at = datetime.datetime.now(datetime.UTC)
            await self.db.commit()

    async def verify_email(self, token: str) -> None:
        payload = helper.verify_token(token, "email_verify")
        key = f"purpose:email_verify:{helper.hash_token(token)}"
        if not await self.redis.getdel(key):
            raise HTTPException(401, "Токен подтверждения уже использован или истек")
        user = await self.db.get(User, int(payload["sub"]))
        if not user:
            raise HTTPException(404, "Пользователь не найден")
        user.email_verified = True
        await self.db.commit()

    async def request_password_reset(self, email: str) -> None:
        user = await self.db.scalar(select(User).where(User.email == email.lower()))
        if not user:
            return
        token = helper.create_purpose_token(user.id, "password_reset", 30)
        await self.redis.set(f"purpose:password_reset:{helper.hash_token(token)}", user.id, ex=30 * 60)
        if not self.email_provider:
            raise HTTPException(503, "Email provider не настроен")
        await self.email_provider.send(
            user.email,
            "Сброс пароля Ayakun",
            f"{settings.frontend_url}/auth/reset-password?token={token}",
        )

    async def reset_password(self, token: str, password: str) -> None:
        payload = helper.verify_token(token, "password_reset")
        key = f"purpose:password_reset:{helper.hash_token(token)}"
        if not await self.redis.getdel(key):
            raise HTTPException(401, "Токен сброса уже использован или истек")
        user = await self.db.get(User, int(payload["sub"]))
        if not user:
            raise HTTPException(404, "Пользователь не найден")
        user.password_hash = helper.hash_password(password)
        await self.db.execute(
            RefreshToken.__table__.update()
            .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.datetime.now(datetime.UTC))
        )
        await self.db.commit()

    async def telegramRegister(self, chat_id: int, name: str) -> User:
        user = User(chat_id=chat_id, name=name)
        self.db.add(user)
        await self.db.flush()
        self.db.add(AuthIdentity(user_id=user.id, provider=IdentityProvider.telegram, subject=str(chat_id)))
        await self.db.commit()
        return user

    async def telegramLoginByCode(self, code: str) -> TokenPair:
        key = f"telegram_login_code:{helper.hash_token(code.strip().upper())}"
        chat_id = await self.redis.getdel(key)
        if not chat_id:
            raise HTTPException(401, "Неверный код")
        user = await self.db.scalar(select(User).where(User.chat_id == int(chat_id)))
        if not user:
            raise HTTPException(401, "Пользователь не найден")
        return await self._tokens(user)

    async def create_google_state(self, redirect_uri: str | None) -> tuple[str, str]:
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        await self.redis.set(
            f"oauth:google:{state}",
            json.dumps({"nonce": nonce, "redirect_uri": redirect_uri}),
            ex=10 * 60,
        )
        return state, nonce

    async def google_login(
        self,
        code: str,
        code_verifier: str,
        state: str,
        redirect_uri: str | None,
    ) -> TokenPair:
        if not settings.google_client_id or not settings.google_client_secret or not self.http_client:
            raise HTTPException(503, "Google OAuth не настроен")
        state_payload = await self.redis.getdel(f"oauth:google:{state}")
        if not state_payload:
            raise HTTPException(401, "Google OAuth state недействителен")
        state_data = json.loads(state_payload)
        expected_redirect_uri = state_data.get("redirect_uri") or settings.google_redirect_uri
        if redirect_uri and redirect_uri != expected_redirect_uri:
            raise HTTPException(401, "Google redirect URI не совпадает")
        response = await self.http_client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": expected_redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
        )
        if response.is_error:
            raise HTTPException(401, "Google authorization code недействителен")
        raw_id_token = response.json().get("id_token")
        if not raw_id_token:
            raise HTTPException(401, "Google не вернул ID token")
        try:
            profile = await asyncio.to_thread(
                google_id_token.verify_oauth2_token,
                raw_id_token,
                GoogleRequest(),
                settings.google_client_id,
            )
        except ValueError as exc:
            raise HTTPException(401, "Google ID token недействителен") from exc
        if profile.get("nonce") != state_data.get("nonce"):
            raise HTTPException(401, "Google OAuth nonce не совпадает")
        if not profile.get("email_verified"):
            raise HTTPException(401, "Google email не подтвержден")
        identity = await self.db.scalar(select(AuthIdentity).where(
            AuthIdentity.provider == IdentityProvider.google, AuthIdentity.subject == profile["sub"]
        ))
        user = await self.db.get(User, identity.user_id) if identity else None
        if not user:
            email = profile.get("email", "").lower() or None
            user = await self.db.scalar(select(User).where(User.email == email)) if email else None
            if not user:
                user = User(name=profile.get("name") or "Google user", email=email, email_verified=True)
                self.db.add(user)
                await self.db.flush()
            self.db.add(AuthIdentity(user_id=user.id, provider=IdentityProvider.google, subject=profile["sub"]))
        return await self._tokens(user)
