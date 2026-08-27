from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from backend.adapters import SQLiteAdapter
from backend.api import auth_router, databases_router, query_router, tables_router
from backend.api.auth import COOKIE_NAME, verify_token
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

    @app.middleware("http")
    async def require_login(request: Request, call_next):
        path = request.url.path
        public = path in {"/login", "/api/health", "/api/auth/login"} or path.startswith("/assets/")
        if not public and not verify_token(request.cookies.get(COOKIE_NAME)):
            if path.startswith("/api/"):
                return JSONResponse(status_code=401, content=fail("AUTH_REQUIRED", "请先登录"))
            return RedirectResponse("/login", status_code=307)
        return await call_next(request)

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

    app.include_router(auth_router)
    app.include_router(databases_router)
    app.include_router(tables_router)
    app.include_router(query_router)

    @app.get("/api/health")
    def health():
        return ok({"status": "ok"})

    @app.get("/login", response_class=HTMLResponse, include_in_schema=False)
    def login_page():
        return HTMLResponse("""<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>登录 db-console</title><style>body{margin:0;background:#f5f7fa;color:#1f2937;font:14px system-ui,sans-serif;display:grid;place-items:center;height:100vh}.box{width:320px;background:#fff;border:1px solid #dfe3e8;padding:28px;box-shadow:0 8px 30px #1f29371a}h1{font-size:20px;margin:0 0 22px}input,button{box-sizing:border-box;width:100%;height:38px;margin:7px 0;padding:0 10px;border:1px solid #cbd5e1}button{background:#2563eb;color:#fff;border:0;cursor:pointer}.error{height:20px;color:#dc2626}</style><div class='box'><h1>登录 db-console</h1><form id='form'><input id='username' placeholder='用户名' autocomplete='username' required><input id='password' type='password' placeholder='密码' autocomplete='current-password' required><div class='error' id='error'></div><button>登录</button></form></div><script>form.onsubmit=async(e)=>{e.preventDefault();error.textContent='';const r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:username.value,password:password.value})});const j=await r.json();if(r.ok&&j.success)location='/';else error.textContent=j.error?.message||'登录失败'}</script></html>""")

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
