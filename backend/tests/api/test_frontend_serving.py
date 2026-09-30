"""Entrega del frontend desde el backend (mismo origen, CSP estricta, caché correcta)."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_spa_is_served_with_strict_csp(tmp_path: Path, test_settings: Settings) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    client = TestClient(create_app(test_settings.model_copy(update={"frontend_dist": tmp_path})))

    page = client.get("/mesa")  # ruta del cliente → index.html
    assert page.status_code == 200
    assert "id=root" in page.text
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert page.headers["cache-control"] == "no-cache"

    asset = client.get("/assets/index-abc123.js")
    assert "immutable" in asset.headers["cache-control"]
    assert client.get("/favicon.svg").status_code == 200

    missing_api = client.get("/api/v1/no-existe")
    assert missing_api.status_code == 404
    assert missing_api.json()["code"] == "NOT_FOUND"
    assert client.get("/api/v1/health").json()["status"] == "ok"
