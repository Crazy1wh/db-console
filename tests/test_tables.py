def data(response):
    payload = response.json()
    assert response.status_code < 400, payload
    assert payload == {"success": True, "data": payload["data"], "error": None}
    return payload["data"]


def test_table_metadata_structure_and_indexes(client):
    tables = data(client.get("/api/databases/sample.sqlite3/tables"))
    users = next(item for item in tables if item["name"] == "users")
    assert users["row_count"] == 3

    structure = data(client.get("/api/databases/sample.sqlite3/tables/users/structure"))
    assert [column["name"] for column in structure] == ["id", "name", "age", "note"]
    assert structure[0]["primary_key"] is True

    indexes = data(client.get("/api/databases/sample.sqlite3/tables/users/indexes"))
    assert any(index["name"] == "idx_users_name" for index in indexes)


def test_rows_pagination_search_sort_columns_and_filters(client):
    response = client.get(
        "/api/databases/sample.sqlite3/tables/users/rows",
        params={
            "page": 1,
            "page_size": 1,
            "search": "Ali",
            "sort_by": "age",
            "sort_order": "desc",
            "columns": "id,name,age",
            "filters": '[{"column":"age","operator":">=","value":30}]',
        },
    )
    result = data(response)
    assert result["total"] == 2
    assert result["columns"] == ["id", "name", "age"]
    assert result["rows"] == [{"id": 3, "name": "Alicia", "age": 40}]


def test_null_filter_and_crud_use_primary_key(client):
    result = data(
        client.get(
            "/api/databases/sample.sqlite3/tables/users/rows",
            params={"filters": '[{"column":"note","operator":"NULL"}]'},
        )
    )
    assert result["total"] == 1
    assert result["rows"][0]["name"] == "Alice"

    inserted = data(
        client.post(
            "/api/databases/sample.sqlite3/tables/users/rows",
            json={"values": {"name": "Cara", "age": 28, "note": None}},
        )
    )
    assert inserted["row"]["name"] == "Cara"
    row_id = inserted["identity"]

    updated = data(
        client.put(
            "/api/databases/sample.sqlite3/tables/users/rows",
            json={"identity": row_id, "values": {"age": 29}},
        )
    )
    assert updated["row"]["age"] == 29

    data(
        client.request(
            "DELETE",
            "/api/databases/sample.sqlite3/tables/users/rows",
            json={"identity": row_id},
        )
    )
    result = data(client.get("/api/databases/sample.sqlite3/tables/users/rows?search=Cara"))
    assert result["total"] == 0


def test_rowid_identity_is_used_when_table_has_no_primary_key(client):
    rows = data(client.get("/api/databases/sample.sqlite3/tables/logs/rows"))
    assert rows["identity_type"] == "rowid"
    identity = rows["rows"][0]["__rowid__"]
    updated = data(
        client.put(
            "/api/databases/sample.sqlite3/tables/logs/rows",
            json={"identity": {"rowid": identity}, "values": {"message": "changed"}},
        )
    )
    assert updated["row"]["message"] == "changed"


def test_identifier_injection_is_rejected(client):
    response = client.get("/api/databases/sample.sqlite3/tables/users%22%3B%20DROP%20TABLE%20users%3B--/rows")
    assert response.status_code == 404
    assert data(client.get("/api/databases/sample.sqlite3/tables/users/rows"))["total"] == 3

