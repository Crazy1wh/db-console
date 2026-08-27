from __future__ import annotations

import json
from typing import Any

from backend.adapters.sqlite import SQLiteAdapter
from backend.errors import AppError


FILTER_OPERATORS = {
    "contains": "LIKE",
    "equals": "=",
    "=": "=",
    "not equals": "!=",
    "!=": "!=",
    ">": ">",
    ">=": ">=",
    "<": "<",
    "<=": "<=",
}


class TableService:
    def __init__(self, adapter: SQLiteAdapter):
        self.adapter = adapter

    def list(self, database: str) -> list[dict]:
        result = []
        with self.adapter.connect(database) as connection:
            for name in self.adapter.table_names(database):
                quoted = self.adapter.quote_identifier(name)
                row_count = connection.execute(f"SELECT COUNT(*) FROM {quoted}").fetchone()[0]
                result.append({"name": name, "row_count": row_count})
        return result

    def structure(self, database: str, table: str) -> list[dict]:
        return self.adapter.columns(database, table)

    def indexes(self, database: str, table: str) -> list[dict]:
        quoted = self.adapter.ensure_table(database, table)
        with self.adapter.connect(database) as connection:
            index_rows = connection.execute(f"PRAGMA index_list({quoted})").fetchall()
            result = []
            for index in index_rows:
                index_name = index["name"]
                quoted_index = self.adapter.quote_identifier(index_name)
                columns = connection.execute(f"PRAGMA index_info({quoted_index})").fetchall()
                result.append(
                    {
                        "name": index_name,
                        "unique": bool(index["unique"]),
                        "origin": index["origin"],
                        "partial": bool(index["partial"]),
                        "columns": [column["name"] for column in columns],
                    }
                )
        return result

    def create(self, database: str, table: str, columns: list[dict]) -> dict:
        if not table.strip() or table in self.adapter.table_names(database):
            raise AppError(400, "INVALID_TABLE", "Table name is empty or already exists")
        if not columns:
            raise AppError(400, "INVALID_COLUMNS", "At least one column is required")
        definitions = []
        seen = set()
        allowed_types = {"INTEGER", "REAL", "TEXT", "BLOB", "NUMERIC"}
        for column in columns:
            name = str(column.get("name", "")).strip()
            data_type = str(column.get("type", "TEXT")).upper()
            if not name or name in seen or data_type not in allowed_types:
                raise AppError(400, "INVALID_COLUMNS", "Column names must be unique and types must be valid SQLite types")
            seen.add(name)
            part = f"{self.adapter.quote_identifier(name)} {data_type}"
            if column.get("primary_key"):
                part += " PRIMARY KEY"
            if column.get("not_null"):
                part += " NOT NULL"
            definitions.append(part)
        sql = f"CREATE TABLE {self.adapter.quote_identifier(table)} ({', '.join(definitions)})"
        with self.adapter.connect(database) as connection:
            connection.execute(sql)
        return {"name": table, "created": True}

    def drop(self, database: str, table: str, confirm: bool) -> dict:
        if not confirm:
            raise AppError(400, "CONFIRMATION_REQUIRED", "DROP TABLE requires confirm=true")
        quoted = self.adapter.ensure_table(database, table)
        with self.adapter.connect(database) as connection:
            connection.execute(f"DROP TABLE {quoted}")
        return {"name": table, "deleted": True}

    def rows(
        self,
        database: str,
        table: str,
        page: int,
        page_size: int,
        search: str | None,
        sort_by: str | None,
        sort_order: str,
        selected_columns: str | None,
        filters_json: str | None,
    ) -> dict:
        quoted_table = self.adapter.ensure_table(database, table)
        metadata = self.adapter.columns(database, table)
        all_columns = [column["name"] for column in metadata]
        columns = [item.strip() for item in selected_columns.split(",") if item.strip()] if selected_columns else all_columns
        self.adapter.ensure_columns(database, table, columns)
        pk_columns = [column["name"] for column in sorted(metadata, key=lambda item: item["pk_position"]) if column["primary_key"]]
        params: list[Any] = []
        clauses: list[str] = []

        if search:
            searchable = all_columns
            clauses.append("(" + " OR ".join(f"CAST({self.adapter.quote_identifier(col)} AS TEXT) LIKE ?" for col in searchable) + ")")
            params.extend([f"%{search}%"] * len(searchable))

        if filters_json:
            try:
                filters = json.loads(filters_json)
            except (json.JSONDecodeError, TypeError) as exc:
                raise AppError(400, "INVALID_FILTERS", "Filters must be a JSON array") from exc
            if not isinstance(filters, list):
                raise AppError(400, "INVALID_FILTERS", "Filters must be a JSON array")
            for item in filters:
                column = str(item.get("column", ""))
                self.adapter.ensure_columns(database, table, [column])
                operator = str(item.get("operator", "equals")).strip()
                normalized = operator.lower()
                quoted_column = self.adapter.quote_identifier(column)
                if normalized in {"null", "is null"}:
                    clauses.append(f"{quoted_column} IS NULL")
                elif normalized in {"not null", "is not null"}:
                    clauses.append(f"{quoted_column} IS NOT NULL")
                elif normalized in FILTER_OPERATORS:
                    sql_operator = FILTER_OPERATORS[normalized]
                    clauses.append(f"{quoted_column} {sql_operator} ?")
                    value = item.get("value")
                    params.append(f"%{value}%" if normalized == "contains" else value)
                else:
                    raise AppError(400, "INVALID_OPERATOR", f"Unsupported filter operator '{operator}'")

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        order = ""
        if sort_by:
            self.adapter.ensure_columns(database, table, [sort_by])
            direction = "DESC" if sort_order.lower() == "desc" else "ASC"
            order = f" ORDER BY {self.adapter.quote_identifier(sort_by)} {direction}"
        elif pk_columns:
            order = " ORDER BY " + ", ".join(self.adapter.quote_identifier(column) for column in pk_columns)

        select_parts = [self.adapter.quote_identifier(column) for column in columns]
        if not pk_columns:
            select_parts.insert(0, "rowid AS __rowid__")
        offset = (page - 1) * page_size
        with self.adapter.connect(database) as connection:
            total = connection.execute(f"SELECT COUNT(*) FROM {quoted_table}{where}", params).fetchone()[0]
            rows = connection.execute(
                f"SELECT {', '.join(select_parts)} FROM {quoted_table}{where}{order} LIMIT ? OFFSET ?",
                [*params, page_size, offset],
            ).fetchall()
        return {
            "rows": [dict(row) for row in rows],
            "columns": columns,
            "total": total,
            "page": page,
            "page_size": page_size,
            "identity_type": "primary_key" if pk_columns else "rowid",
            "primary_keys": pk_columns,
        }

    def insert(self, database: str, table: str, values: dict[str, Any]) -> dict:
        quoted_table = self.adapter.ensure_table(database, table)
        if not values:
            raise AppError(400, "EMPTY_VALUES", "At least one value is required")
        columns = list(values)
        self.adapter.ensure_columns(database, table, columns)
        quoted_columns = ", ".join(self.adapter.quote_identifier(column) for column in columns)
        placeholders = ", ".join("?" for _ in columns)
        with self.adapter.connect(database) as connection:
            cursor = connection.execute(
                f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({placeholders})",
                [values[column] for column in columns],
            )
            rowid = cursor.lastrowid
        identity = self._identity_from_rowid(database, table, rowid)
        return {"identity": identity, "row": self._fetch_identity(database, table, identity)}

    def update(self, database: str, table: str, identity: dict[str, Any], values: dict[str, Any]) -> dict:
        quoted_table = self.adapter.ensure_table(database, table)
        if not values:
            raise AppError(400, "EMPTY_VALUES", "At least one value is required")
        columns = list(values)
        self.adapter.ensure_columns(database, table, columns)
        where, identity_params = self._identity_clause(database, table, identity)
        assignments = ", ".join(f"{self.adapter.quote_identifier(column)} = ?" for column in columns)
        with self.adapter.connect(database) as connection:
            cursor = connection.execute(
                f"UPDATE {quoted_table} SET {assignments} WHERE {where}",
                [*[values[column] for column in columns], *identity_params],
            )
            if cursor.rowcount != 1:
                raise AppError(404, "ROW_NOT_FOUND", "Row was not found or identity is not unique")
        new_identity = dict(identity)
        for key in list(new_identity):
            if key in values:
                new_identity[key] = values[key]
        return {"identity": new_identity, "row": self._fetch_identity(database, table, new_identity)}

    def delete(self, database: str, table: str, identity: dict[str, Any]) -> dict:
        quoted_table = self.adapter.ensure_table(database, table)
        where, params = self._identity_clause(database, table, identity)
        with self.adapter.connect(database) as connection:
            cursor = connection.execute(f"DELETE FROM {quoted_table} WHERE {where}", params)
            if cursor.rowcount != 1:
                raise AppError(404, "ROW_NOT_FOUND", "Row was not found or identity is not unique")
        return {"deleted": True, "identity": identity}

    def _identity_from_rowid(self, database: str, table: str, rowid: int) -> dict[str, Any]:
        metadata = self.adapter.columns(database, table)
        pk_columns = [item["name"] for item in sorted(metadata, key=lambda item: item["pk_position"]) if item["primary_key"]]
        if not pk_columns:
            return {"rowid": rowid}
        quoted_table = self.adapter.ensure_table(database, table)
        select = ", ".join(self.adapter.quote_identifier(column) for column in pk_columns)
        with self.adapter.connect(database) as connection:
            row = connection.execute(f"SELECT {select} FROM {quoted_table} WHERE rowid = ?", [rowid]).fetchone()
        return {column: row[column] for column in pk_columns}

    def _identity_clause(self, database: str, table: str, identity: dict[str, Any]):
        metadata = self.adapter.columns(database, table)
        pk_columns = [item["name"] for item in sorted(metadata, key=lambda item: item["pk_position"]) if item["primary_key"]]
        if pk_columns:
            if set(identity) != set(pk_columns):
                raise AppError(400, "INVALID_IDENTITY", f"Identity must contain primary key(s): {', '.join(pk_columns)}")
            return " AND ".join(f"{self.adapter.quote_identifier(column)} IS ?" for column in pk_columns), [identity[column] for column in pk_columns]
        if set(identity) != {"rowid"}:
            raise AppError(400, "INVALID_IDENTITY", "Identity must contain rowid")
        return "rowid = ?", [identity["rowid"]]

    def _fetch_identity(self, database: str, table: str, identity: dict[str, Any]) -> dict:
        quoted_table = self.adapter.ensure_table(database, table)
        where, params = self._identity_clause(database, table, identity)
        with self.adapter.connect(database) as connection:
            row = connection.execute(f"SELECT * FROM {quoted_table} WHERE {where}", params).fetchone()
        if row is None:
            raise AppError(404, "ROW_NOT_FOUND", "Row was not found")
        return dict(row)
