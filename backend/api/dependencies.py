from fastapi import Request

from backend.services import DatabaseService, QueryService, TableService


def database_service(request: Request) -> DatabaseService:
    return request.app.state.database_service


def table_service(request: Request) -> TableService:
    return request.app.state.table_service


def query_service(request: Request) -> QueryService:
    return request.app.state.query_service
