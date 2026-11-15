#!/bin/sh
# Container entrypoint: apply migrations, then start uvicorn.
# Forwarded headers are trusted only from the proxies listed in TRUSTED_PROXY_IPS; when it is
# empty they are ignored so a client cannot spoof its IP (and dodge the login rate limit).
set -e
alembic upgrade head
if [ -n "${TRUSTED_PROXY_IPS:-}" ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
    --proxy-headers --forwarded-allow-ips "$TRUSTED_PROXY_IPS"
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-proxy-headers
