import sqlite3

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def db_root(tmp_path, monkeypatch):
    root = tmp_path / "databases"
    root.mkdir()
    db = root / "sample.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                age INTEGER,
                note TEXT
            );
            CREATE INDEX idx_users_name ON users(name);
            INSERT INTO users(name, age, note) VALUES
                ('Alice', 31, NULL),
                ('Bob', 24, 'long note'),
                ('Alicia', 40, 'admin');
            CREATE TABLE logs (message TEXT);
            INSERT INTO logs(message) VALUES ('first');
            """
        )
    (root / "ignore.txt").write_text("not a database", encoding="utf-8")
    monkeypatch.setenv("DB_ROOT", str(root))
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    return root


@pytest.fixture()
def client(db_root):
    from backend.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client

