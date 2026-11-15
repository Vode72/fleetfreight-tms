# FleetFreight backend

FastAPI + SQLAlchemy 2 (sync, psycopg 3) + Alembic + PostgreSQL. Python 3.15, managed with `uv`.

## Run with Docker Compose

```bash
cp .env.example .env      # from the repository root
docker compose up --build
curl http://localhost:8000/health   # {"status":"ok","database":"ok"}
```

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
