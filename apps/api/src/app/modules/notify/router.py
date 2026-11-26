"""实时推送 HTTP 端点（阶段 4.2 / 4.3）。

- ``GET /api/v1/notify/stream``：SSE，Web 三端使用（fetch 流式 + Bearer 头）；
- ``WS  /api/v1/notify/ws``：小程序使用（JWT 走 query，微信 socket 不便自定义头）。

鉴权：SSE 复用 ``get_current_user``（含黑名单校验）；WS 手动 decode + 黑名单校验，
均从**可信 Token** 取 tenant_id / user_id，不接受前端传入的身份参数。
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.core.exceptions import AuthException, BusinessException
from app.core.security import decode_token, is_token_blacklisted
from app.deps.auth import get_current_user, get_redis_client
from app.modules.notify.bus import bus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notify", tags=["实时推送"])

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    # 防止 Nginx 缓冲（阶段 4.5）
    "X-Accel-Buffering": "no",
}


@router.get("/stream")
async def stream(
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """SSE 订阅当前用户（含租户）的状态变更信号。"""
    tenant_id = int(current_user["tenant_id"])
    user_id = int(current_user["user_id"])
    heartbeat = get_settings().NOTIFY_HEARTBEAT_SECONDS

    if not bus.acquire(tenant_id, user_id):
        raise BusinessException("实时连接数超限，请关闭多余页面后重试", code=429)

    queue = bus.subscribe(tenant_id, user_id)

    async def event_generator():
        try:
            # 客户端断线后 3s 重连
            yield "retry: 3000\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=heartbeat)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except TimeoutError:
                    yield ": ping\n\n"
        finally:
            bus.unsubscribe(tenant_id, user_id, queue)
            bus.release(tenant_id, user_id)

    return StreamingResponse(
        event_generator(), media_type="text/event-stream", headers=SSE_HEADERS
    )


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="access_token"),
) -> None:
    """小程序 WebSocket 订阅（JWT 走 query，握手期完成认证/吊销校验）。"""
    payload = decode_token(token)
    if payload is None:
        await websocket.close(code=4401)
        return
    try:
        redis = await get_redis_client()
        if await is_token_blacklisted(token, redis):
            await websocket.close(code=4401)
            return
    except AuthException:
        await websocket.close(code=1011)
        return

    tenant_id = int(payload["tenant_id"])
    user_id = int(payload["user_id"])
    heartbeat = get_settings().NOTIFY_HEARTBEAT_SECONDS

    if not bus.acquire(tenant_id, user_id):
        await websocket.close(code=4429)
        return

    queue = bus.subscribe(tenant_id, user_id)
    await websocket.accept()
    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=heartbeat)
                await websocket.send_text(json.dumps(event, ensure_ascii=False))
            except TimeoutError:
                await websocket.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.exception("[notify] WebSocket 异常 tenant=%s user=%s", tenant_id, user_id)
    finally:
        bus.unsubscribe(tenant_id, user_id, queue)
        bus.release(tenant_id, user_id)
