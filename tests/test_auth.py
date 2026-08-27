def test_login_protects_api_and_sets_session_cookie(monkeypatch, tmp_path):
    import sqlite3
    from fastapi.testclient import TestClient

    root = tmp_path / "data"
    root.mkdir()
    sqlite3.connect(root / "sample.db").close()
    monkeypatch.setenv("DB_ROOT", str(root))
    monkeypatch.setenv("AUTH_USERNAME", "admin")
    monkeypatch.setenv("AUTH_PASSWORD", "secret")
    monkeypatch.setenv("SESSION_SECRET", "test-secret")

    from backend.main import create_app

    with TestClient(create_app()) as client:
        denied = client.get("/api/databases")
        assert denied.status_code == 401
        assert denied.json()["error"]["code"] == "AUTH_REQUIRED"

        bad = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
        assert bad.status_code == 401

        logged_in = client.post("/api/auth/login", json={"username": "admin", "password": "secret"})
        assert logged_in.status_code == 200
        assert logged_in.json()["success"] is True
        assert "db_console_session" in logged_in.cookies

        allowed = client.get("/api/databases")
        assert allowed.status_code == 200
        assert allowed.json()["success"] is True

        client.post("/api/auth/logout")
        assert client.get("/api/databases").status_code == 401


def test_login_page_is_public():
    from fastapi.testclient import TestClient
    from backend.main import create_app

    with TestClient(create_app()) as client:
        response = client.get("/login")
        assert response.status_code == 200
        assert "登录 db-console" in response.text
