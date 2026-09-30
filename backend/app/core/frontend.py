"""Entrega del frontend (build de Vite) desde el mismo proceso y origen que la API.

- /assets/*: archivos con hash en el nombre → caché inmutable de 1 año.
- Cualquier otra ruta que no sea /api → index.html (enrutamiento del lado del cliente), sin caché.
- Content-Security-Policy estricta: sin scripts externos ni inline.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

from app.core.config import API_PREFIX
from app.core.errors import error_response

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; "
    "object-src 'none'"
)


class ImmutableStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def mount_frontend(app: FastAPI, dist: Path) -> None:
    index = dist / "index.html"
    if not index.is_file():
        raise RuntimeError(f"FRONTEND_DIST no contiene index.html: {dist}")
    if (dist / "assets").is_dir():
        app.mount("/assets", ImmutableStaticFiles(directory=dist / "assets"), name="assets")
    root_files = {p.name for p in dist.iterdir() if p.is_file() and p.name != "index.html"}

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str, request: Request) -> Response:
        if full_path.startswith(API_PREFIX.lstrip("/")):
            return error_response(404, "NOT_FOUND")
        if full_path in root_files:  # favicon.svg, robots.txt, etc.
            return FileResponse(dist / full_path, headers={"Cache-Control": "public, max-age=86400"})
        return FileResponse(index, headers={"Cache-Control": "no-cache", "Content-Security-Policy": CSP})
