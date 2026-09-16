import httpx
import redis.asyncio as redis
from services.telegram import TelegramService
from deps.database import get_db, get_redis
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends, Request
from services.user import UserService
from services.auth import AuthService
from services.billing import BillingService
from services.providers import SMTPEmailProvider, YooKassaProvider
from services.admin_records import AdminRecordsService
from services.workflow import WorkflowService


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db=db)

def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client

def get_auth_service(
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> AuthService:
    return AuthService(
        db=db,
        redis_client=redis_client,
        http_client=http_client,
        email_provider=SMTPEmailProvider(),
    )

def get_telegram_service(db: AsyncSession = Depends(get_db), redis: redis.Redis = Depends(get_redis), userService: UserService = Depends(get_user_service), authService: AuthService = Depends(get_auth_service), http_client: httpx.AsyncClient = Depends(get_http_client)) -> TelegramService:
    return TelegramService(db=db, redis=redis, userService=userService, authService=authService, http_client=http_client)

def get_workflow_service(db: AsyncSession = Depends(get_db)) -> WorkflowService:
    return WorkflowService(db, BillingService(db))

def get_billing_service(
    db: AsyncSession = Depends(get_db),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> BillingService:
    return BillingService(db, YooKassaProvider(http_client))


def get_admin_records_service(
    db: AsyncSession = Depends(get_db),
) -> AdminRecordsService:
    return AdminRecordsService(db, BillingService(db))