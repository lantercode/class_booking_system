"""AI 写操作确认令牌（无状态、防篡改、短时效）。

令牌只承载「拟执行」内容，不承载任何业务判断；确认接口校验令牌后
再通过 ``execute_tool`` → Service 走真实业务链路。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

from app.core.config import get_settings

DEFAULT_TTL_SECONDS = 300


class ActionTokenError(Exception):
    """令牌无效 / 过期 / 身份不匹配。"""


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(body: str, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()


def issue_action_token(
    *,
    action: str,
    payload: dict[str, Any],
    user_id: int,
    tenant_id: int,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> str:
    secret = get_settings().JWT_SECRET
    body = _b64encode(
        json.dumps(
            {
                "jti": uuid.uuid4().hex,
                "action": action,
                "payload": payload,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "exp": int(time.time()) + ttl_seconds,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    )
    return f"{body}.{_sign(body, secret)}"


def verify_action_token(
    token: str,
    *,
    user_id: int,
    tenant_id: int,
) -> dict[str, Any]:
    secret = get_settings().JWT_SECRET
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise ActionTokenError("确认令牌格式无效") from exc

    if not hmac.compare_digest(_sign(body, secret), signature):
        raise ActionTokenError("确认令牌校验失败")

    try:
        data = json.loads(_b64decode(body))
    except (ValueError, TypeError) as exc:
        raise ActionTokenError("确认令牌格式无效") from exc

    if data.get("exp", 0) < int(time.time()):
        raise ActionTokenError("确认已过期，请重新发起")
    if data.get("user_id") != user_id or data.get("tenant_id") != tenant_id:
        raise ActionTokenError("确认令牌与当前登录身份不匹配")

    if not isinstance(data.get("action"), str) or not isinstance(data.get("payload"), dict):
        raise ActionTokenError("确认令牌内容无效")
    return data
