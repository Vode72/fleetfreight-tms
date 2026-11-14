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
