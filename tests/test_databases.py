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

