from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.adapters import SQLiteAdapter
from backend.api import databases_router, query_router, tables_router
from backend.errors import AppError
from backend.responses import fail, ok
from backend.services import DatabaseService, QueryService, TableService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def create_app() -> FastAPI:
    app = FastAPI(title="db-console", version="0.1.0")
    db_root = os.getenv("DB_ROOT", str(PROJECT_ROOT / "data"))
    adapter = SQLiteAdapter(db_root)
    app.state.adapter = adapter
    app.state.database_service = DatabaseService(adapter)
    app.state.table_service = TableService(adapter)
    app.state.query_service = QueryService(adapter)

    origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if item.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=fail(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content=fail("VALIDATION_ERROR", "Request validation failed", exc.errors()))

    @app.exception_handler(sqlite3.Error)
    async def sqlite_error_handler(_request: Request, exc: sqlite3.Error):
        return JSONResponse(status_code=400, content=fail("SQLITE_ERROR", str(exc)))

    app.include_router(databases_router)
    app.include_router(tables_router)
    app.include_router(query_router)

    @app.get("/api/health")
    def health():
        return ok({"status": "ok"})

    dist = PROJECT_ROOT / "frontend" / "dist"
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            return JSONResponse(status_code=404, content=fail("NOT_FOUND", "API endpoint not found"))
        requested = (dist / path).resolve()
        if dist.is_dir():
            try:
                requested.relative_to(dist.resolve())
                if requested.is_file():
                    return FileResponse(requested)
            except ValueError:
                pass
            index = dist / "index.html"
            if index.is_file():
                return FileResponse(index)
        return JSONResponse(status_code=404, content=fail("NOT_FOUND", "Frontend build not found"))

    return app


app = create_app()
