"""One error shape for every failure: {"error": {"code", "message"}}."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("rxvision")

STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media",
    422: "validation_error",
    429: "rate_limited",
}


class ApiError(Exception):
    def __init__(self, status: int, message: str, code: str | None = None):
        self.status = status
        self.message = message
        self.code = code or STATUS_CODES.get(status, "error")


def _envelope(status: int, code: str, message: str, headers=None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message}},
        headers=headers,
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError):
        return _envelope(exc.status, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return _envelope(
            exc.status_code,
            STATUS_CODES.get(exc.status_code, "error"),
            message,
            getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        return _envelope(422, "validation_error", friendly_validation_message(first))


def friendly_validation_message(error: dict) -> str:
    """Turn a pydantic error into a sentence a person can act on."""
    loc = [str(p) for p in error.get("loc", []) if p not in ("body", "query", "path")]
    field = loc[-1] if loc else ""
    kind = error.get("type", "")
    ctx = error.get("ctx") or {}
    label = field.replace("_", " ").capitalize() or "Value"

    if field == "email" and kind != "missing":
        return "Enter a valid email address"
    if kind == "missing":
        return f"{label} is required"
    if kind == "string_too_short":
        n = ctx.get("min_length", 1)
        return f"{label} is required" if n == 1 else f"{label} must be at least {n} characters"
    if kind == "string_too_long":
        return f"{label} must be at most {ctx.get('max_length')} characters"
    message = str(error.get("msg", "is invalid")).removeprefix("Value error, ")
    return f"{label}: {message}" if field else message

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("unhandled error", exc_info=exc)
        return _envelope(500, "internal", "Something went wrong on our side")
