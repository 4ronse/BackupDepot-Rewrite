import logging
from typing import Any, Generic, Literal, TypeVar

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)
T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    status: Literal["OK", "ERROR"] = "OK"
    message: str = "OK"
    data: T | None = None


class ValidationErrorItem(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


def ok(status_code: int = 200, message: str = 'Success', data=None, headers=None) -> JSONResponse:
    body = ResponseModel(status='OK', message=message, data=data)
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body), headers=headers)

def error(status_code: int, message: str, data=None, headers=None) -> JSONResponse:
    body = ResponseModel(status="ERROR", message=message, data=data)
    return JSONResponse(status_code=status_code, content=jsonable_encoder(body), headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        if isinstance(exc.detail, dict):
            message: str = exc.detail.get('message')  # type: ignore
            data: Any = exc.detail.get('data')  # type: ignore
            return error(exc.status_code, message, data, exc.headers)
        return error(exc.status_code, str(exc.detail), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        items = [ValidationErrorItem(loc=list(e["loc"]), msg=e["msg"], type=e["type"]) for e in exc.errors()]
        return error(422, "Validation failed", items)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return error(500, "Internal server error")
