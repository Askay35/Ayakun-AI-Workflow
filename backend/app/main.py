from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from api.v1.router import router
from starlette.exceptions import HTTPException as StarletteHTTPException
from core.config import settings
from core.exceptions import http_exception_handler
from core.logging import RequestLoggingMiddleware, setup_logging
import httpx
import redis.asyncio as redis

setup_logging("backend")

_docs_enabled = settings.environment == "development"


async def lifespan(app: FastAPI):
    app.state.redis = await redis.from_url(settings.redis_url, decode_responses=True)
    app.state.http_client = httpx.AsyncClient()
    
    yield

    await app.state.redis.aclose()
    await app.state.http_client.aclose()

app = FastAPI(
    lifespan=lifespan,
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
)

app.add_middleware(RequestLoggingMiddleware, skip_paths=frozenset({"/healthz"}))
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


@app.get("/healthz", include_in_schema=False)
async def healthz() -> PlainTextResponse:
    return PlainTextResponse("ok")
