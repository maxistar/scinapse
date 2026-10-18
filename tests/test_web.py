from pathlib import Path

from fastapi.testclient import TestClient

from scinapse.web import create_web_app


def test_production_app_serves_frontend_and_api_from_one_origin(tmp_path: Path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html><body>Scinapse</body></html>", encoding="utf-8")
    (tmp_path / "assets" / "app.js").write_text("console.log('ok')", encoding="utf-8")

    with TestClient(create_web_app(tmp_path)) as client:
        assert client.get("/").status_code == 200
        assert client.get("/").text == "<html><body>Scinapse</body></html>"
        assert client.get("/assets/app.js").status_code == 200
        assert client.get("/api/health").json()["status"] == "ok"
        assert client.get("/api/does-not-exist").status_code == 404
