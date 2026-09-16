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
from schemas.user import UserResponse
from services.google_oauth import gmail_scope_string, save_gmail_grant, user_response
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
        if loaded is None:
            raise HTTPException(401, "Пользователь недоступен")
        return TokenPair(
            access_token=helper.generate_token(user.id),
            refresh_token=raw,
            user=await user_response(self.db, loaded),
        )

    async def impersonate(self, user_id: int) -> TokenPair:
        user = await self.db.scalar(
            select(User).options(selectinload(User.identities)).where(User.id == user_id)
        )
        if not user:
            raise HTTPException(404, "Пользователь не найден")
        if not user.is_active:
            raise HTTPException(403, "Пользователь отключён")
        return await self._tokens(user)

    async def request_email_register(self, email: str, password: str, name: str) -> None:
        email = email.lower()
        if not self.email_provider:
            raise HTTPException(503, "Email provider не настроен")
        if await self.db.scalar(select(User).where(User.email == email)):
            raise HTTPException(409, "Email уже используется")
        rate_key = f"email_register_rate:{email}"
        attempts = await self.redis.incr(rate_key)
        if attempts == 1:
            await self.redis.expire(rate_key, 60)
        if attempts > 5:
            raise HTTPException(429, "Слишком много запросов кода")
        code = helper.generate_login_code()
        ttl = 60 * settings.login_code_expiration_time
        await self.redis.set(
            f"email_register_pending:{email}",
            json.dumps({
                "name": name,
                "password_hash": helper.hash_password(password),
                "code_hash": helper.hash_token(code),
            }),
            ex=ttl,
        )
        await self.email_provider.send(
            email,
            "Код подтверждения Ayakun",
            (
                f"Ваш код для регистрации: {code}\n\n"
                f"Он действителен в течение {settings.login_code_expiration_time} минут."
            ),
        )

    async def confirm_email_register(self, email: str, code: str) -> TokenPair:
        email = email.lower()
        pending_key = f"email_register_pending:{email}"
        pending_raw = await self.redis.get(pending_key)
        if not pending_raw:
            raise HTTPException(401, "Неверный код")
        pending = json.loads(pending_raw)
        code_hash = helper.hash_token(code.strip().upper())
        if not secrets.compare_digest(str(pending.get("code_hash") or ""), code_hash):
            raise HTTPException(401, "Неверный код")
        await self.redis.delete(pending_key)
        if await self.db.scalar(select(User).where(User.email == email)):
            raise HTTPException(409, "Email уже используется")
        user = User(
            name=pending["name"],
            email=email,
            password_hash=pending["password_hash"],
            email_verified=True,
        )
        self.db.add(user)
        await self.db.flush()
        self.db.add(AuthIdentity(user_id=user.id, provider=IdentityProvider.email, subject=email))
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
        chat_id, name = await self._consume_telegram_code(code)
        user = await self.db.scalar(select(User).where(User.chat_id == chat_id))
        if not user:
            user = await self.telegramRegister(chat_id, name)
        return await self._tokens(user)

    async def telegram_link_by_code(self, user: User, code: str) -> UserResponse:
        chat_id, _name = await self._consume_telegram_code(code)
        existing = await self.db.scalar(select(User).where(User.chat_id == chat_id))
        if existing and existing.id != user.id:
            raise HTTPException(409, "Этот Telegram уже используется")
        if user.chat_id and user.chat_id != chat_id:
            raise HTTPException(409, "Telegram уже подключён")
        user.chat_id = chat_id
        has_identity = any(item.provider == IdentityProvider.telegram for item in user.identities)
        if not has_identity:
            self.db.add(AuthIdentity(user_id=user.id, provider=IdentityProvider.telegram, subject=str(chat_id)))
        await self.db.commit()
        loaded = await self.db.scalar(
            select(User).options(selectinload(User.identities)).where(User.id == user.id)
        )
        if loaded is None:
            raise HTTPException(401, "Пользователь недоступен")
        return await user_response(self.db, loaded)

    async def _consume_telegram_code(self, code: str) -> tuple[int, str]:
        key = f"telegram_login_code:{helper.hash_token(code.strip().upper())}"
        raw = await self.redis.getdel(key)
        if not raw:
            raise HTTPException(401, "Неверный код")
        if isinstance(raw, bytes):
            raw = raw.decode()
        text = str(raw)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            payload = {"chat_id": text}
        if isinstance(payload, dict):
            chat_id = int(payload.get("chat_id"))
            name = str(payload.get("name") or "Telegram").strip() or "Telegram"
        else:
            chat_id = int(payload)
            name = "Telegram"
        return chat_id, name

    async def create_google_state(
        self,
        redirect_uri: str | None,
        *,
        purpose: str = "login",
        user_id: int | None = None,
    ) -> tuple[str, str]:
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        payload: dict = {"nonce": nonce, "redirect_uri": redirect_uri, "purpose": purpose}
        if user_id is not None:
            payload["user_id"] = user_id
        await self.redis.set(
            f"oauth:google:{state}",
            json.dumps(payload),
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
        token_payload = response.json()
        raw_id_token = token_payload.get("id_token")
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
        if state_data.get("purpose") == "gmail":
            return await self._google_link_gmail(profile, token_payload, state_data)
        if state_data.get("purpose") == "link":
            return await self._google_link_identity(profile, state_data)
        return await self._google_upsert_user(profile)

    async def _google_upsert_user(self, profile: dict) -> TokenPair:
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

    async def _google_link_identity(self, profile: dict, state_data: dict) -> TokenPair:
        user_id = state_data.get("user_id")
        if not user_id:
            raise HTTPException(401, "Google OAuth state недействителен")
        user = await self.db.scalar(
            select(User).options(selectinload(User.identities)).where(User.id == int(user_id))
        )
        if not user or not user.is_active:
            raise HTTPException(401, "Пользователь недоступен")
        subject = profile["sub"]
        identity = await self.db.scalar(select(AuthIdentity).where(
            AuthIdentity.provider == IdentityProvider.google, AuthIdentity.subject == subject
        ))
        if identity and identity.user_id != user.id:
            raise HTTPException(409, "Этот Google-аккаунт уже используется")
        own = next((item for item in user.identities if item.provider == IdentityProvider.google), None)
        if own and own.subject != subject:
            raise HTTPException(409, "Google уже подключён")
        if not own:
            self.db.add(AuthIdentity(user_id=user.id, provider=IdentityProvider.google, subject=subject))
        if not user.email:
            email = (profile.get("email") or "").lower() or None
            if email and not await self.db.scalar(select(User).where(User.email == email)):
                user.email = email
                user.email_verified = True
        return await self._tokens(user)

    async def _google_link_gmail(self, profile: dict, token_payload: dict, state_data: dict) -> TokenPair:
        user_id = state_data.get("user_id")
        if not user_id:
            raise HTTPException(401, "Google OAuth state недействителен")
        user = await self.db.scalar(
            select(User).options(selectinload(User.identities)).where(User.id == int(user_id))
        )
        if not user or not user.is_active:
            raise HTTPException(401, "Пользователь недоступен")
        email = (profile.get("email") or "").lower() or None
        scopes = token_payload.get("scope") or gmail_scope_string()
        account = await save_gmail_grant(
            self.db,
            user,
            google_sub=profile["sub"],
            email=email,
            refresh_token=token_payload.get("refresh_token"),
            scopes=scopes if isinstance(scopes, str) else " ".join(scopes),
        )
        pair = await self._tokens(user)
        return pair.model_copy(update={"gmail_account": {"id": account.id, "email": account.email}})
