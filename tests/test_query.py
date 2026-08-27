def result(response):
    payload = response.json()
    assert response.status_code < 400, payload
    assert payload["success"] is True
    return payload["data"]


def test_parameterized_select_and_mutation(client):
    selected = result(
        client.post(
            "/api/query",
            json={"database": "sample.sqlite3", "sql": "SELECT name FROM users WHERE age > ?", "params": [30]},
        )
    )
    assert selected["columns"] == ["name"]
    assert [row["name"] for row in selected["rows"]] == ["Alice", "Alicia"]

    mutation = result(
        client.post(
            "/api/query",
            json={"database": "sample.sqlite3", "sql": "UPDATE users SET note = ? WHERE name = ?", "params": ["ok", "Bob"]},
        )
    )
    assert mutation["affected_rows"] == 1


def test_dangerous_sql_requires_explicit_confirmation(client):
    for sql in (
        "DROP TABLE logs",
        "VACUUM",
        "ATTACH DATABASE ':memory:' AS extra",
    ):
        denied = client.post("/api/query", json={"database": "sample.sqlite3", "sql": sql})
        assert denied.status_code == 400
        assert "confirm" in denied.json()["error"]["message"].lower()

    result(
        client.post(
            "/api/query",
            json={"database": "sample.sqlite3", "sql": "DROP TABLE logs", "confirm": True},
        )
    )


def test_drop_database_text_is_also_guarded(client):
    denied = client.post(
        "/api/query",
        json={"database": "sample.sqlite3", "sql": "-- DROP DATABASE anything\nSELECT 1"},
    )
    assert denied.status_code == 400


def test_cors_and_error_envelope(client):
    response = client.options(
        "/api/databases",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"

    response = client.get("/api/databases/missing.db/tables")
    assert response.status_code == 404
    assert response.json()["success"] is False
    assert response.json()["data"] is None
    assert response.json()["error"]["code"]
