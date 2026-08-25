# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-tenant SaaS for dance studios. Monorepo containing 5 apps:

| App | Role | Stack | Port |
|---|---|---|---|
| `apps/api` | Backend REST API | FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL 15 + Redis 7 | 8000 |
| `apps/admin-web` | Management console | Vue 3 + Vite + Element Plus + Pinia | 5173 |
| `apps/student-web` | Student web portal | Vue 3 + Vite + Element Plus | 5174 |
| `apps/teacher-web` | Teacher web portal | Vue 3 + Vite + Element Plus | 5175 |
| `apps/miniapp` | WeChat MiniProgram (student + teacher, dual-role) | uni-app + Vue 3 + TypeScript | — |

Shared code lives in `packages/`:
- `api-client` — axios wrapper with token refresh + tenant header injection (baseURL is relative `/api/v1`, consumed by all web apps)
- `api-types` — TypeScript types generated from FastAPI OpenAPI schema (regenerate with `pnpm gen:types`)
- `utils`, `config`, `shared-ui` — cross-app helpers

## Common Commands

**Repo root (pnpm + Turborepo orchestration):**
```bash
pnpm install                        # Install JS deps for all workspaces
pnpm db:up                          # Start Postgres + Redis (docker compose infra/docker/docker-compose.yml)
pnpm db:down                        # Stop them
pnpm dev:api                        # Start backend only
pnpm dev:student                    # Start student-web only
pnpm dev                            # Start EVERYTHING via turbo (usually too much)
pnpm gen:types                      # Regenerate packages/api-types/schema.d.ts from FastAPI OpenAPI
pnpm build                          # Build all apps
pnpm lint / pnpm test               # Turbo-fan-out to each app
```

**Backend (`apps/api`, Python 3.12 via `uv`):**
```bash
cd apps/api
uv sync                             # Install Python deps (uses pyproject.toml + uv.lock)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir src
uv run alembic upgrade head         # Apply migrations
uv run alembic revision --autogenerate -m "msg"   # Create migration (must import new models in alembic/env.py first)
uv run python scripts/seed.py       # Seed default tenant + admin (phone 12345678901)
uv run pytest                       # Run all tests
uv run pytest tests/integration/test_auth_api.py -v   # Single test file
uv run pytest -k test_login         # Filter by test name
uv run ruff check src tests         # Lint
```

**Admin web (`apps/admin-web`):**
```bash
cd apps/admin-web
pnpm dev                            # Vite dev server on :5173 (proxies /api → http://localhost:8000)
pnpm build                          # vue-tsc + vite build → dist/
```

**MiniProgram (`apps/miniapp`):**
```bash
cd apps/miniapp
npm install                         # NOTE: miniapp uses npm, not pnpm (uni-app quirk)
npm run dev:mp-weixin               # Watch build → dist/dev/mp-weixin/, open in WeChat DevTools
npm run build:mp-weixin             # Production build → dist/build/mp-weixin/
```

## Backend Architecture (must-know)

**DDD-style layering per module.** Each `apps/api/src/app/modules/<name>/` has 4 files:
- `router.py` — FastAPI routes (thin, just param validation + permission decorators)
- `service.py` — Business logic + transactions
- `repository.py` — Data access, extends `TenantAwareRepository` from `app/core/base_repository.py` for auto tenant scoping
- `schemas.py` — Pydantic request/response models

Modules registered in `app/main.py` under prefix `/api/v1`. AI module registers its own `/api/v1/ai` prefix.

**Multi-tenancy** — the load-bearing pattern in this codebase:
- Middleware `app/middleware/tenant_middleware.py` (pure ASGI, NOT `BaseHTTPMiddleware` — avoids asyncio bugs) reads `x-tenant-id` or `x-tenant-slug` header, sets `ContextVar`
- `app/core/tenant_query.py::setup_tenant_query_injection()` is called in the `lifespan` and auto-injects `WHERE tenant_id = ?` on all queries against tenant-scoped models
- All repositories that hold tenant data MUST extend `TenantAwareRepository[Model]` — never write raw queries that bypass it
- Skip-list paths (docs, health, auth register/login) are defined at the top of `tenant_middleware.py`

**Auth** — JWT dual-token (access 2h + refresh 7d) with Redis blacklist:
- `app/core/security.py` — encode/decode + password hashing (bcrypt)
- `app/deps/auth.py` — FastAPI dependencies: `get_current_user`, `get_redis_client`
- Token uniqueness enforced by `iat` (microsecond) + `jti` (UUIDv4)
- Logout / token-rotation adds JTI to Redis blacklist with TTL = remaining token lifetime
- Redis is **mandatory in production** — `lifespan` in `main.py` raises `RuntimeError` if unreachable

**RBAC** — `app/core/rbac/`:
- Permissions stored per-role, cached in Redis, invalidated on role change
- Use `@require_permissions("resource:action")` on router handlers
- Standard actions: `create / read / update / delete`, plus `role:assign`, `user:reset_password`, etc.

**Error handling** — `DanceSaasException` → `dance_saas_exception_handler` returns unified `{code, msg, data}` shape.

**Response envelope** — all endpoints return `{code: int, msg: str, data: T}` (see `app/core/response.py`). Frontend `packages/api-client/src/index.ts` unwraps this.

## Frontend Conventions

- `packages/api-client/src/index.ts:18` — `API_BASE = '/api/v1'` is a **relative path** by design. Nginx same-origin reverse-proxies in prod; Vite dev proxy handles dev. Do NOT hardcode absolute URLs in web apps.
- Miniapp is different: uses absolute `VITE_API_BASE_URL` because it's compiled to WeChat runtime, no browser same-origin. See `apps/miniapp/src/api/index.ts:1`.
- 401 → auto-refresh via `refresh_token` → retry original request → on refresh failure clear localStorage + redirect to `/login`.
- Tenant slug lives in `localStorage.tenantSlug`, injected as `x-tenant-slug` header by the axios interceptor.

## Migrations Workflow (bites people)

1. Add/edit a model in `apps/api/src/app/modules/<name>/models.py`
2. **Import it in `apps/api/alembic/env.py`** — otherwise `--autogenerate` won't see it
3. `cd apps/api && uv run alembic revision --autogenerate -m "add xxx"`
4. Review the generated file in `apps/api/alembic/versions/` (autogen sometimes misses index/enum changes)
5. `uv run alembic upgrade head`
6. If the generated migration is broken and you want to redo: `alembic downgrade -1` then delete the file

## AI Agent Module

`app/ai/` + `app/modules/ai/router.py` implement a chat-based booking assistant:
- MCP Server exposes booking tools (`create_booking`, `cancel_booking`, `list_schedules`, etc.)
- `AgentRuntime` handles multi-turn dialog with tool calling
- Miniapp UI: `apps/miniapp/src/components/AiAssistant.vue`
- API paths: `POST /api/v1/ai/chat`, `GET /api/v1/ai/history`, `DELETE /api/v1/ai/clear`

## Testing Notes

- Integration tests spin up a real Uvicorn server on port 8765 in a background thread (see `apps/api/tests/conftest.py`) — this was the fix for asyncpg event-loop conflicts with `ASGITransport`. Don't try to switch back to in-process test client.
- Tests require Postgres + Redis running (`pnpm db:up`).
- Tests hit a real DB, no mocks — schema is created fresh per session.

## Deployment

Production deployment is documented in `/Users/lixiang/.cogen/claude/plans/glistening-discovering-book.md` (Docker Compose + Nginx + Let's Encrypt on Alibaba Cloud ECS). Files to know:
- `apps/api/Dockerfile` — backend image
- `infra/docker/docker-compose.prod.yml` — production stack
- `infra/docker/.env.prod.example` — env template (real `.env.prod` is gitignored)
- `infra/nginx/nginx.conf` — production HTTPS reverse-proxy (`admin.` + `api.` subdomains)
- `infra/nginx/nginx.stage-a.conf` — pre-ICP-approval IP-only fallback

## Repo-Specific Gotchas

- `apps/miniapp` uses `npm` (not `pnpm`) due to uni-app's quirks with pnpm hoisting
- Backend uses `redirect_slashes=False` — trailing slash matters, `/courses` ≠ `/courses/`. When calling from frontend, don't append trailing slash to collection endpoints
- `apps/api/scripts/seed.py` default admin phone is `12345678901`, tenant slug is `dance-school` (tenant_id=2)
- `.env.prod` and `.env.production` are gitignored — never commit real secrets
- WeChat AppSecret must come from environment (`WECHAT_SECRET` in `.env.prod`), never hardcoded in `apps/api/src/app/core/config.py`
