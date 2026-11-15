"""User roles. Pure domain module (no framework or database imports)."""

from enum import StrEnum


class Role(StrEnum):
    """Application roles. The values are stored in the database (see the users CHECK constraint)."""

    ADMIN = "admin"
    PLANNER = "planner"
    VIEWER = "viewer"
