"""Helpers to build consistent JSON API responses."""
from typing import Any, Dict, Optional


def success(data: Any = None, meta: Optional[Dict[str, Any]] = None, status: int = 200):
    from flask import jsonify
    # If data already contains a status key assume caller formed payload
    if isinstance(data, dict) and 'status' in data and meta is None:
        return jsonify(data), status
    payload: Dict[str, Any] = {"status": "success"}
    if data is not None:
        payload.update(data if isinstance(data, dict) else {"data": data})
    if meta is not None:
        payload["meta"] = meta
    return jsonify(payload), status


def error(message: str, status: int = 400, code: Optional[str] = None, details: Any = None):
    from flask import jsonify
    payload: Dict[str, Any] = {"status": "error", "message": message}
    if code:
        payload["code"] = code
    if details is not None:
        payload["details"] = details
    return jsonify(payload), status


def not_found(message: str = "Resource not found"):
    return error(message, status=404, code="not_found")


def server_error(message: str = "Internal server error", details: Any = None):
    return error(message, status=500, code="server_error", details=details)
