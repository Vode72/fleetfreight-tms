"""The ONLY list of routes that may be called without a session.

Every other route is protected by the global dependency in `app.auth.deps` (secure by default).
A new public route must be added here deliberately and will show up in code review.
Entries are (HTTP method, route path as declared, i.e. with path parameters like `{id}`).
"""

PUBLIC_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        # Container healthchecks and monitoring; exposes only ok/error.
        ("GET", "/health"),
        # Obtaining a session obviously cannot require one.
        ("POST", "/auth/login"),
    }
)
# Interactive docs (/docs, /redoc, /openapi.json) are registered by FastAPI itself and exist
# only when ENVIRONMENT=development (see create_app).
