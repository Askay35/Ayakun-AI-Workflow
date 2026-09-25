# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Ayakun — SaaS for visual AI automation (n8n-like, fewer integrations, no user-owned AI subscriptions). Users build a node chain in a visual editor; it runs on a schedule, via a webhook node, or manually. Users pay for a subscription with a Russian bank card (YooKassa); the owner pays providers (DeepSeek, GigaChat, Serper, …) and earns on the spread between internal Ayakun credits and provider token cost. Project docs and UI are primarily in Russian.

- `backend/app` — Python 3.13, FastAPI, Celery, SQLAlchemy 2 (async, asyncpg), Pydantic v2, Alembic, managed with `uv`
- `frontend` — Nuxt 3 / Vue 3 / TypeScript, Nuxt UI + Tailwind 4, Vue Flow for the editor
- Infra: PostgreSQL, Redis (cache/temp state), RabbitMQ (Celery broker), Loki/Promtail/Grafana for logs

## Commands

Everything runs through Docker Compose; `.env` must exist (copy `.env.example`). Inside containers `DB_URL`/`REDIS_URL`/`CELERY_BROKER_URL` must point to `postgres`/`redis`/`rabbitmq` hosts, not localhost.

```bash
scripts/dev.sh up        # start infra, run migrations, start backend/worker/beat/frontend (hot reload)
scripts/dev.sh migrate   # alembic upgrade head only
scripts/dev.sh logs      # follow logs; also: down, status
```

Backend (from `backend/app`):

```bash
uv sync --dev
uv run pytest -q
uv run pytest tests/test_pricing.py::test_deepseek_flash_credit_conversion -q   # single test
uv run alembic revision -m "msg"    # new migration (all schema changes go through Alembic)
```

Frontend (from `frontend`): `npm run dev`, `npm run typecheck`, `npm run build`. No lint or frontend test tooling is configured.

Dev URLs: app `:3000`, OpenAPI `:8000/docs` (only when `ENVIRONMENT=development`), RabbitMQ UI `:15672`, Grafana `:3001`. Deploy is via `.github/workflows/deploy.yml` and `docker-compose.prod.yml` / `scripts/prod.sh`.

## Architecture

**Request flow:** `api/v1/*` routers → `services/*` (constructor-injected, composed via `deps/services.py` with `Depends()`) → SQLAlchemy `AsyncSession` directly (no repository layer unless needed). Transaction boundaries live in services. Long-lived `redis` and `httpx.AsyncClient` are created in the FastAPI lifespan (`main.py`) and stored on `app.state`. Config is `pydantic-settings` in `core/config.py`. `backend/app` is the Python root (imports are `from services...`, `from models...`; pytest `pythonpath = ["."]`).

**Workflow graph:** stored as a list of nodes with no edge array; links are encoded as `parents`/`children` id lists on each node and kept symmetric by the backend on parse (see `docs/workflow-graph.md`, `schemas/workflow.py`). A workflow has a mutable `draft_graph` and an immutable published `graph_snapshot`; every run uses a snapshot. The graph must be a valid DAG before publish. Node types are the `NodeType` enum plus one Pydantic `*Node` model each.

**Execution:** `execution/tasks.py` holds Celery tasks (`execute_workflow`, `poll_scheduled_workflows` run by beat every 60s) and `WorkflowRunExecutor`, which walks nodes in topological order, passes parent outputs as context, handles retries, cancellation, if/else branch skipping, and persists `NodeRun` records. Node implementations are in `services/execution/actions/*`; `services/execution/executors.py` (`DefaultExecutors`) wires each action to its dependencies and registers it in `NodeRegistry` (`registry.py`). Adding a node type means touching: `NodeType` + node schema, an action, `DefaultExecutors`/registry, pricing (`node_cost` / `services/pricing.py`), and the frontend editor (`WorkflowNodeCard.vue`, `utils/workflow-graph.ts`, i18n `ru.ts`/`en.ts`).

**Billing (critical invariants):** users hold a wallet of credits (`models/billing.py`, `services/billing/*`). Before a run, credits are atomically reserved (PostgreSQL row locks) so concurrent runs can't overspend; LLM input tokens are estimated locally with the DeepSeek tokenizer (`utils/deepseek_tokenizer.py`), the max output size is derived from the remaining budget, and after execution the actual usage (cache-hit/miss/output tokens) is charged and the unused reserve released. Financial operations carry a `request_id` for idempotency (Celery uses `acks_late`, so tasks can be redelivered) and are ledgered. Pricing/margins live in `services/pricing.py` and runtime settings tables (many Alembic migrations tune credit rates and plans).

**Providers:** `services/providers.py` (`ModelRouter`, `WebSearchRouter`, Telegram), `gigachat.py`, `deepseek_vision.py`, `google_oauth.py`, YooKassa in `services/billing/payments.py`. Auth: JWT access/refresh (explicit algorithms), email, Google OAuth, Telegram login; admin permissions in `deps/admin.py`.

**Frontend:** file-based `pages/`, layouts (`default`, `app`, `editor`), composables `useApi`/`useAuth`, own lightweight i18n (`i18n/ru.ts`, `en.ts`, `composables/useI18n.ts` — add keys to both). `types/api.ts` mirrors backend schemas; editor canvas is `components/WorkflowEditorCanvas.vue`. The editor is unavailable on mobile (`useIsMobileEditor`).

## Conventions (from `.claude/rules` and `.cursor/rules`)

- Smallest correct change, minimal diff; reuse existing patterns; don't refactor unrelated code or add abstractions/dependencies without concrete need.
- **Don't add tests unless asked.**
- Async everywhere on request paths (`httpx.AsyncClient`, `redis.asyncio`, `AsyncSession`); timezone-aware UTC datetimes; modern type hints, avoid `Any`.
- Pydantic schemas for all API I/O; versioned routers under `/api/v1`; external webhooks must return quickly and defer work to Celery.
- Never hardcode secrets; config via env.
- No comments that merely restate the code.
