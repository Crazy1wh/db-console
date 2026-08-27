from __future__ import annotations

import sqlite3

from backend.adapters.sqlite import ALLOWED_EXTENSIONS, SQLiteAdapter
from backend.errors import AppError


class DatabaseService:
    def __init__(self, adapter: SQLiteAdapter):
        self.adapter = adapter

    def list(self) -> list[dict]:
        databases = []
        for path in self.adapter.root.rglob("*"):
            if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS:
                databases.append(
                    {
                        "name": path.relative_to(self.adapter.root).as_posix(),
                        "size_bytes": path.stat().st_size,
                        "modified_at": path.stat().st_mtime,
                    }
                )
        return sorted(databases, key=lambda item: item["name"].lower())

    def create(self, name: str) -> dict:
        path = self.adapter.resolve_database(name, must_exist=False)
        if path.exists():
            raise AppError(409, "DATABASE_EXISTS", f"Database '{name}' already exists")
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as connection:
            connection.execute("PRAGMA user_version = 0")
        return {"name": path.relative_to(self.adapter.root).as_posix(), "size_bytes": path.stat().st_size}

    def delete(self, name: str, confirm: bool) -> dict:
        if not confirm:
            raise AppError(400, "CONFIRMATION_REQUIRED", "DROP DATABASE requires confirm=true")
        path = self.adapter.resolve_database(name)
        path.unlink()
        return {"name": name, "deleted": True}

    def stats(self, name: str) -> dict:
        path = self.adapter.resolve_database(name)
        table_names = self.adapter.table_names(name)
        counts = []
        with self.adapter.connect(name) as connection:
            for table in table_names:
                quoted = self.adapter.quote_identifier(table)
                count = connection.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
                counts.append({"table": table, "row_count": count})
            page_count = connection.execute("PRAGMA page_count").fetchone()[0]
            page_size = connection.execute("PRAGMA page_size").fetchone()[0]
        return {
            "name": name,
            "size_bytes": path.stat().st_size,
            "allocated_bytes": page_count * page_size,
            "table_count": len(table_names),
            "row_count": sum(item["row_count"] for item in counts),
            "tables": counts,
        }
