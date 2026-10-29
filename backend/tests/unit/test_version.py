"""La versión del sistema es una sola: backend (pyproject.toml), frontend (package.json) y /health."""

import json
import tomllib
from pathlib import Path

from app.main import VERSION

ROOT = Path(__file__).resolve().parents[3]


def test_backend_and_frontend_versions_match() -> None:
    backend = tomllib.loads((ROOT / "backend" / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    frontend = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))["version"]
    assert backend == frontend, "Actualice la versión en backend/pyproject.toml y frontend/package.json a la vez"
    assert backend == VERSION
