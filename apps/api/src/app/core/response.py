"""统一响应包装 - 所有 API 返回 { code, data, msg, request_id }."""
from typing import Any, Generic, TypeVar
from uuid import uuid4

from pydantic import BaseModel, Field

T = TypeVar("T")


class StandardResponse(BaseModel, Generic[T]):
    code: int = 0
    data: T | None = None
    msg: str = "ok"
    request_id: str = Field(default_factory=lambda: f"req_{uuid4().hex[:16]}")


def success(data: Any = None, msg: str = "ok") -> dict:
    return {
        "code": 0,
        "data": data,
        "msg": msg,
        "request_id": f"req_{uuid4().hex[:16]}",
    }


def fail(code: int, msg: str, errors: list[dict] | None = None) -> dict:
    return {
        "code": code,
        "data": None,
        "msg": msg,
        "request_id": f"req_{uuid4().hex[:16]}",
        **({"errors": errors} if errors else {}),
    }
