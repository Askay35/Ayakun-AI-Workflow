FROM python:3.13-slim AS runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_CACHE_DIR=/tmp/uv-cache \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"

COPY --from=ghcr.io/astral-sh/uv:0.8.15 /uv /uvx /bin/
COPY backend/app/pyproject.toml backend/app/uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project \
    && addgroup --system --gid 10001 app \
    && adduser --system --uid 10001 --ingroup app --home /app app \
    && mkdir -p /var/lib/celery /tmp/uv-cache \
    && chown -R app:app /app /opt/venv /var/lib/celery /tmp/uv-cache

COPY --chown=app:app backend/app/ .

EXPOSE 8000

USER app

CMD ["uv", "run", "--no-sync", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]