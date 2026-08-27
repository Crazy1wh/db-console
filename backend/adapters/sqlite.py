from __future__ import annotations

import sqlite3
import os
from pathlib import Path
from typing import Any, Sequence

from backend.adapters.base import DatabaseAdapter
from backend.errors import AppError


ALLOWED_EXTENSIONS = {".db", ".sqlite", ".sqlite3"}


class SQLiteAdapter(DatabaseAdapter):
    def __init__(self, root: str | Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.external_root = Path(os.getenv("DB_EXTERNAL_ROOT", "/external")).resolve()
        self.host_root = Path(os.getenv("DB_HOST_ROOT", "")).expanduser().resolve() if os.getenv("DB_HOST_ROOT") else None
        self.registered: dict[str, Path] = {}
        self.catalog_path = Path(os.getenv("DB_CATALOG", str(self.root / ".db-console-catalog.sqlite3"))).expanduser().resolve()
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.catalog_path) as catalog:
            catalog.execute("CREATE TABLE IF NOT EXISTS registrations (name TEXT PRIMARY KEY, path TEXT NOT NULL)")
        self._load_registered()

    def _load_registered(self) -> None:
        with sqlite3.connect(self.catalog_path) as catalog:
            rows = catalog.execute("SELECT name, path FROM registrations").fetchall()
        for name, path in rows:
            candidate = Path(path).resolve()
            if candidate.is_file() and candidate.suffix.lower() in ALLOWED_EXTENSIONS:
                self.registered[name] = candidate

    def register_database(self, requested: str) -> str:
        raw = Path(requested).expanduser()
        if not raw.is_absolute():
            candidate = (self.root / raw).resolve()
            name = candidate.relative_to(self.root).as_posix()
        elif self.host_root and raw.resolve().is_relative_to(self.host_root):
            candidate = (self.external_root / raw.resolve().relative_to(self.host_root)).resolve()
            name = candidate.relative_to(self.external_root).as_posix()
            name = f"external:{name}"
        else:
            candidate = raw.resolve()
            if candidate.is_relative_to(self.root):
                name = candidate.relative_to(self.root).as_posix()
            elif candidate.is_relative_to(self.external_root):
                name = f"external:{candidate.relative_to(self.external_root).as_posix()}"
            else:
                raise AppError(400, "PATH_NOT_ALLOWED", "路径不在 DB_ROOT 或配置的外部根目录内")
        if candidate.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise AppError(400, "INVALID_DATABASE", "只支持 .db、.sqlite、.sqlite3")
        if not candidate.is_file():
            raise AppError(404, "DATABASE_NOT_FOUND", f"文件不存在或容器不可见: {requested}")
        self.registered[name] = candidate
        with sqlite3.connect(self.catalog_path) as catalog:
            catalog.execute("INSERT OR REPLACE INTO registrations(name, path) VALUES (?, ?)", (name, str(candidate)))
        return name

    def resolve_database(self, database: str, *, must_exist: bool = True) -> Path:
        if not database or "\x00" in database:
            raise AppError(400, "INVALID_DATABASE", "Invalid database path")
        if database in self.registered:
            candidate = self.registered[database]
            if must_exist and not candidate.is_file():
                raise AppError(404, "DATABASE_NOT_FOUND", f"Database '{database}' was not found")
            return candidate
        if database.startswith("external:"):
            relative = Path(database.removeprefix("external:"))
            candidate = (self.external_root / relative).resolve()
            try:
                candidate.relative_to(self.external_root)
            except ValueError as exc:
                raise AppError(400, "PATH_TRAVERSAL", "外部数据库路径越界") from exc
            if must_exist and not candidate.is_file():
                raise AppError(404, "DATABASE_NOT_FOUND", f"Database '{database}' was not found")
            return candidate
        relative = Path(database)
        if relative.is_absolute() or relative.suffix.lower() not in ALLOWED_EXTENSIONS:
            raise AppError(400, "INVALID_DATABASE", "Database must be under DB_ROOT with a supported extension")
        candidate = (self.root / relative).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise AppError(400, "PATH_TRAVERSAL", "Database path escapes DB_ROOT") from exc
        if must_exist and (not candidate.is_file() or candidate.suffix.lower() not in ALLOWED_EXTENSIONS):
            raise AppError(404, "DATABASE_NOT_FOUND", f"Database '{database}' was not found")
        return candidate

    def connect(self, database: str) -> sqlite3.Connection:
        path = self.resolve_database(database)
        connection = sqlite3.connect(path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def execute(self, database: str, sql: str, params: Sequence[Any] = ()):
        with self.connect(database) as connection:
            cursor = connection.execute(sql, tuple(params))
            rows = cursor.fetchall() if cursor.description else []
            return cursor, rows

    @staticmethod
    def quote_identifier(identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    def table_names(self, database: str) -> list[str]:
        with self.connect(database) as connection:
            rows = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        return [row["name"] for row in rows]

    def ensure_table(self, database: str, table: str) -> str:
        if table not in self.table_names(database):
            raise AppError(404, "TABLE_NOT_FOUND", f"Table '{table}' was not found")
        return self.quote_identifier(table)

    def columns(self, database: str, table: str) -> list[dict]:
        quoted = self.ensure_table(database, table)
        with self.connect(database) as connection:
            rows = connection.execute(f"PRAGMA table_info({quoted})").fetchall()
        return [
            {
                "cid": row["cid"],
                "name": row["name"],
                "type": row["type"] or "",
                "not_null": bool(row["notnull"]),
                "default": row["dflt_value"],
                "primary_key": bool(row["pk"]),
                "pk_position": row["pk"],
            }
            for row in rows
        ]

    def ensure_columns(self, database: str, table: str, columns: Sequence[str]) -> list[str]:
        available = {column["name"] for column in self.columns(database, table)}
        invalid = [column for column in columns if column not in available]
        if invalid:
            raise AppError(400, "INVALID_COLUMN", f"Unknown column(s): {', '.join(invalid)}")
        return list(columns)
