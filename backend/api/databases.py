from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.api.dependencies import database_service
from backend.responses import ok
from backend.services import DatabaseService


router = APIRouter(prefix="/api/databases", tags=["databases"])


class DatabaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


@router.get("")
def list_databases(service: DatabaseService = Depends(database_service)):
    return ok(service.list())


@router.post("")
def create_database(body: DatabaseCreate, service: DatabaseService = Depends(database_service)):
    return ok(service.create(body.name))


@router.delete("/{database}")
def delete_database(database: str, confirm: bool = Query(False), service: DatabaseService = Depends(database_service)):
    return ok(service.delete(database, confirm))


@router.get("/{database:path}/stats")
def database_stats(database: str, service: DatabaseService = Depends(database_service)):
    return ok(service.stats(database))
