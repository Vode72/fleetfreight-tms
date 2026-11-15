"""Write the FastAPI OpenAPI description to a JSON file.

Usage (from the backend directory):
    uv run python -m scripts.export_openapi PATH

Needs no running server and no database connection: building the schema only inspects the
route definitions. Used by CI to check that the generated frontend API types are up to date.
"""

import json
import sys
from pathlib import Path

from app.main import app


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m scripts.export_openapi PATH", file=sys.stderr)
        return 2
    target = Path(argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
