# FleetFreight backend

FastAPI + SQLAlchemy 2 (sync, psycopg 3) + Alembic + PostgreSQL. Python 3.15, managed with `uv`.

## Run with Docker Compose

```bash
cp .env.example .env      # from the repository root; development values only
docker compose up --build
curl http://localhost:8000/health   # {"status":"ok","database":"ok"}
```

`docker-compose.yml` is production-safe: `POSTGRES_PASSWORD` is required (no default),
`ENVIRONMENT` defaults to `production` and `SESSION_COOKIE_SECURE` to `true`. The development
settings (`ENVIRONMENT=development`, non-Secure cookie, `DEMO_PASSWORD`) live in
`docker-compose.override.yml`, which Compose merges automatically with `docker compose up`.
Production must not use it: `docker compose -f docker-compose.yml up -d`.
The app refuses to start with `ENVIRONMENT=production` and `SESSION_COOKIE_SECURE=false`.

### Production start behind a reverse proxy

The container entrypoint (`start.sh`) trusts forwarded headers only from the addresses in
`TRUSTED_PROXY_IPS` (comma separated; empty = trust none, never `*`). It then runs
`uvicorn app.main:app --proxy-headers --forwarded-allow-ips <TRUSTED_PROXY_IPS>`. Without it the
client IP is the proxy's address, so the per-IP login limit would apply to all users together
(the app logs a warning at start). Outside Docker pass the same two uvicorn flags yourself.
The client IP is personal data: it appears in logs on failed and throttled logins (e-mail
addresses are logged only as an HMAC keyed with `LOG_HMAC_KEY`). Keep log retention short.
Set `LOG_HMAC_KEY` to a long random secret; if empty, a random key is generated at each start.

## Known limitations

- The login rate limiter is in memory and per process. It assumes a single worker (the demo
  setup); several workers or instances each count separately, and a restart resets the counters.
  Shared state (database or Redis) is a later step.
- Limits are per IP+e-mail and per IP. A distributed attack from many addresses is not slowed
  down by them; it needs a shared store, an upstream limiter or a WAF.
- Session revocation: any code path that deactivates a user or changes a password must call
  `app.auth.service.revoke_all_sessions` (the demo seed script does; future endpoints must).
- No Content-Security-Policy yet; it comes with static frontend serving in production.

## Local development

```bash
cd backend
uv python install 3.15
uv sync
docker compose up -d db             # or any local PostgreSQL
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

Settings are read from environment variables, then from `.env` in the repository root or in `backend/`.
If the database password contains URL special characters (`@`, `:`, `/`, `#`), URL-encode it in `DATABASE_URL`.

## Authentication

Server-side sessions: `POST /auth/login` (JSON `email`, `password`) answers 204 and sets an httpOnly,
`SameSite=Lax` cookie holding a random token (only its SHA-256 digest is stored). `POST /auth/logout`
revokes the session, `GET /auth/me` returns `id`, `email`, `role`. Roles: `admin`, `planner`, `viewer`.

- Every route requires a session unless listed in `app/auth/public.py`. Use
  `Depends(require_role("admin"))` for role checks.
- Every POST/PUT/PATCH/DELETE (login included) must send `X-Requested-With: fleetfreight`, otherwise 403.
- `/docs`, `/redoc` and `/openapi.json` exist only with `ENVIRONMENT=development`
  (`app.openapi()` and `scripts.export_openapi` work in every environment).
- Demo users (not in migrations; development only):
  `DEMO_PASSWORD=... ENVIRONMENT=development uv run python -m scripts.seed_demo_users`.
  Settings are listed in `.env.example`.

## Tests and quality checks

Tests use a separate database taken from `TEST_DATABASE_URL` (name must end with `_test`;
it is created automatically). The development database is never touched.

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy
```

## New migration

```bash
uv run alembic revision -m "describe the change"
```

## OpenAPI export (no server or database needed)

```bash
uv run python -m scripts.export_openapi /tmp/openapi.json
# then, in frontend/: OPENAPI_URL=/tmp/openapi.json npm run gen:api
```

CI (`api-types.yml`) does the same and fails if `frontend/src/api/schema.ts` differs from the result.
