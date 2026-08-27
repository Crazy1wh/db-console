from __future__ import annotations

import re
import time
from typing import Any

from backend.adapters.sqlite import SQLiteAdapter
from backend.errors import AppError


DANGEROUS_SQL = re.compile(r"\b(?:DROP\s+TABLE|DROP\s+DATABASE|VACUUM|ATTACH(?:\s+DATABASE)?)\b", re.IGNORECASE)


class QueryService:
    def __init__(self, adapter: SQLiteAdapter):
        self.adapter = adapter

    def execute(self, database: str, sql: str, params: list[Any], confirm: bool) -> dict:
        statement = sql.strip()
        if not statement:
            raise AppError(400, "EMPTY_SQL", "SQL statement is required")
        if DANGEROUS_SQL.search(statement) and not confirm:
            raise AppError(400, "CONFIRMATION_REQUIRED", "Dangerous SQL requires confirm=true")
        started = time.perf_counter()
        try:
            with self.adapter.connect(database) as connection:
                cursor = connection.execute(statement, params)
                if cursor.description:
                    columns = [item[0] for item in cursor.description]
                    rows = [dict(row) for row in cursor.fetchall()]
                    result = {"columns": columns, "rows": rows, "row_count": len(rows), "affected_rows": None}
                else:
                    result = {"columns": [], "rows": [], "row_count": 0, "affected_rows": max(cursor.rowcount, 0)}
        except AppError:
            raise
        except Exception as exc:
            raise AppError(400, "SQL_ERROR", str(exc)) from exc
        result["duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
        return result
