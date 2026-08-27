from typing import Any


def ok(data: Any = None) -> dict:
    return {"success": True, "data": data, "error": None}


def fail(code: str, message: str, details: Any = None) -> dict:
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"success": False, "data": None, "error": error}
