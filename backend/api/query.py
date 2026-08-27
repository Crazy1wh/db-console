from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.dependencies import query_service
from backend.responses import ok
from backend.services import QueryService


router = APIRouter(prefix="/api/query", tags=["query"])


class QueryRequest(BaseModel):
    database: str
    sql: str
    params: list[Any] = Field(default_factory=list)
    confirm: bool = False


@router.post("")
def execute_query(body: QueryRequest, service: QueryService = Depends(query_service)):
    return ok(service.execute(body.database, body.sql, body.params, body.confirm))
