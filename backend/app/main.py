from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.v1.router import router
from starlette.exceptions import HTTPException as StarletteHTTPException
from core.config import settings
from core.exceptions import http_exception_handler
from core.logging import setup_logging
import httpx
import redis.asyncio as redis

setup_logging("backend")


async def lifespan(app: FastAPI):
    app.state.redis = await redis.from_url(settings.redis_url, decode_responses=True)
    app.state.http_client = httpx.AsyncClient()
    
    yield

    await app.state.redis.aclose()
    await app.state.http_client.aclose()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(
    StarletteHTTPException,
    http_exception_handler,
)

app.include_router(router)
