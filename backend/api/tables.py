from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.api.dependencies import table_service
from backend.responses import ok
from backend.services import TableService


router = APIRouter(prefix="/api/databases/{database}/tables", tags=["tables"])


class ColumnCreate(BaseModel):
    name: str
    type: str = "TEXT"
    primary_key: bool = False
    not_null: bool = False


class TableCreate(BaseModel):
    name: str
    columns: list[ColumnCreate]


class RowCreate(BaseModel):
    values: dict[str, Any]


class RowUpdate(BaseModel):
    identity: dict[str, Any]
    values: dict[str, Any]


class RowDelete(BaseModel):
    identity: dict[str, Any]


@router.get("")
def list_tables(database: str, service: TableService = Depends(table_service)):
    return ok(service.list(database))


@router.post("")
def create_table(database: str, body: TableCreate, service: TableService = Depends(table_service)):
    return ok(service.create(database, body.name, [column.model_dump() for column in body.columns]))


@router.delete("/{table}")
def drop_table(database: str, table: str, confirm: bool = Query(False), service: TableService = Depends(table_service)):
    return ok(service.drop(database, table, confirm))


@router.get("/{table}/structure")
def table_structure(database: str, table: str, service: TableService = Depends(table_service)):
    return ok(service.structure(database, table))


@router.get("/{table}/indexes")
def table_indexes(database: str, table: str, service: TableService = Depends(table_service)):
    return ok(service.indexes(database, table))


@router.get("/{table}/rows")
def table_rows(
    database: str,
    table: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    search: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "asc",
    columns: str | None = None,
    filters: str | None = None,
    service: TableService = Depends(table_service),
):
    return ok(service.rows(database, table, page, page_size, search, sort_by, sort_order, columns, filters))


@router.post("/{table}/rows")
def insert_row(database: str, table: str, body: RowCreate, service: TableService = Depends(table_service)):
    return ok(service.insert(database, table, body.values))


@router.put("/{table}/rows")
def update_row(database: str, table: str, body: RowUpdate, service: TableService = Depends(table_service)):
    return ok(service.update(database, table, body.identity, body.values))


@router.delete("/{table}/rows")
def delete_row(database: str, table: str, body: RowDelete, service: TableService = Depends(table_service)):
    return ok(service.delete(database, table, body.identity))
