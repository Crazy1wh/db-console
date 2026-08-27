from pathlib import Path


def assert_success(response):
    payload = response.json()
    assert response.status_code < 400, payload
    assert payload["success"] is True
    assert payload["error"] is None
    return payload["data"]


def test_database_scan_create_delete_and_stats(client, db_root: Path):
    databases = assert_success(client.get("/api/databases"))
    assert [item["name"] for item in databases] == ["sample.sqlite3"]

    created = assert_success(client.post("/api/databases", json={"name": "new.db"}))
    assert created["name"] == "new.db"
    assert (db_root / "new.db").is_file()

    stats = assert_success(client.get("/api/databases/sample.sqlite3/stats"))
    assert stats["table_count"] == 2
    assert stats["row_count"] == 4
    assert stats["size_bytes"] > 0

    denied = client.delete("/api/databases/new.db")
    assert denied.status_code == 400
    assert denied.json()["success"] is False
    assert_success(client.delete("/api/databases/new.db?confirm=true"))
    assert not (db_root / "new.db").exists()


def test_database_path_traversal_and_extension_are_rejected(client, db_root: Path):
    outside = db_root.parent / "outside.sqlite3"
    response = client.get("/api/databases/..%2Foutside.sqlite3/tables")
    assert response.status_code in (400, 404)
    assert not outside.exists()

    response = client.post("/api/databases", json={"name": "bad.txt"})
    assert response.status_code == 400
    assert response.json()["success"] is False


def test_register_accepts_host_path_and_maps_to_external_root(monkeypatch, tmp_path):
    import sqlite3
    from fastapi.testclient import TestClient

    host_root = tmp_path / "host"
    external_root = tmp_path / "external"
    host_root.mkdir()
    external_root.mkdir()
    db_path = external_root / "project.sqlite3"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO items(value) VALUES ('ok')")

    monkeypatch.setenv("DB_ROOT", str(tmp_path / "empty"))
    monkeypatch.setenv("DB_HOST_ROOT", str(host_root))
    monkeypatch.setenv("DB_EXTERNAL_ROOT", str(external_root))
    from backend.main import create_app

    with TestClient(create_app()) as test_client:
        test_client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        registered = assert_success(test_client.post("/api/databases/register", json={"path": str(host_root / "project.sqlite3")}))
        assert registered["name"] == "external:project.sqlite3"
        rows = assert_success(test_client.get("/api/databases/external%3Aproject.sqlite3/tables/items/rows"))
        assert rows["rows"][0]["value"] == "ok"

    with TestClient(create_app()) as restarted_client:
        restarted_client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        names = [item["name"] for item in assert_success(restarted_client.get("/api/databases"))]
        assert "external:project.sqlite3" in names
