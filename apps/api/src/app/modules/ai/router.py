"""
AI 智能助手 API 路由

企业级特性：
  - 请求限流（防刷）
  - 认证鉴权（JWT Token）
  - 结构化日志
  - 错误码标准化
  - 响应格式统一

接口列表：
  POST /api/v1/ai/chat          - 发送消息（多轮对话）
  GET  /api/v1/ai/history       - 获取历史记录
  DELETE /api/v1/ai/history     - 清空历史记录
  GET  /api/v1/ai/intents       - 获取支持的意图列表（调试用）
"""

import hashlib
import json
import time
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agent.action_token import ActionTokenError, verify_action_token
from app.ai.agent.runtime import AgentRuntime
from app.ai.mcp_server import TOOL_SPECS, ToolContext, execute_tool, tool_context
from app.core.database import get_session
from app.core.exceptions import BusinessException
from app.deps.auth import get_current_user, get_redis_client
from app.modules.notification.service import record_audit

router = APIRouter(prefix="/api/v1/ai", tags=["AI 智能助手"])

# session_id 只作为 Redis key 的一段：限制字符集与长度，避免超长/特殊字符 key。
# 仍未跨用户：SessionManager 的 key 始终带 user_id 前缀（见 session.py）。
SESSION_ID_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    session_id: str = Field(default="default", pattern=SESSION_ID_PATTERN)


class ConfirmActionRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=4000)


class ChatResponse(BaseModel):
    code: int = 0
    msg: str = "success"
    data: dict | None = None


class HistoryResponse(BaseModel):
    code: int = 0
    msg: str = "success"
    data: list = []


async def get_agent_runtime(
    redis_client=Depends(get_redis_client),
    current_user=Depends(get_current_user),
) -> AgentRuntime:
    return AgentRuntime(
        redis_client=redis_client,
        user_id=current_user.get("user_id") if current_user else None,
        tenant_id=current_user.get("tenant_id") if current_user else None,
        role_id=current_user.get("role_id") if current_user else None,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest, request: Request, agent_runtime: AgentRuntime = Depends(get_agent_runtime)
):
    start_time = time.time()

    response_text = await agent_runtime.chat(user_input=body.message, session_id=body.session_id)

    state = await agent_runtime.session.get_state(body.session_id)
    has_pending_state = bool(state)
    latency_ms = int((time.time() - start_time) * 1000)

    return ChatResponse(
        code=0,
        msg="success",
        data={
            "response": response_text,
            "session_id": body.session_id,
            "timestamp": datetime.now().isoformat(),
            "has_pending_state": has_pending_state,
            "latency_ms": latency_ms,
            "pending_action": getattr(agent_runtime, "pending_action", None),
        },
    )


@router.post("/actions/confirm", response_model=ChatResponse)
async def confirm_action(
    body: ConfirmActionRequest,
    db: AsyncSession = Depends(get_session),
    redis_client=Depends(get_redis_client),
    current_user: dict = Depends(get_current_user),
):
    """两阶段确认：校验令牌 → 幂等 → 通过统一 Tool 入口执行 → 写审计。"""
    user_id = int(current_user["user_id"])
    tenant_id = int(current_user["tenant_id"])

    try:
        data = verify_action_token(body.token, user_id=user_id, tenant_id=tenant_id)
    except ActionTokenError as exc:
        raise BusinessException(str(exc), code=400) from exc

    action = data["action"]
    payload = data["payload"]
    spec = TOOL_SPECS.get(action)
    if spec is None or not spec.is_write:
        raise BusinessException("该操作不允许通过确认接口执行", code=400)

    # 幂等：user_id + action + 参数指纹，24 小时内重复提交只执行一次
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    idem_key = f"ai:idem:{tenant_id}:{user_id}:{action}:{fingerprint}"
    if redis_client is None:
        raise BusinessException("服务暂不可用，请稍后再试", code=503)
    acquired = await redis_client.set(idem_key, "1", nx=True, ex=86400)
    if not acquired:
        raise BusinessException("该操作已处理，请勿重复提交", code=409)

    ctx = ToolContext(
        user_id=user_id,
        tenant_id=tenant_id,
        role_id=current_user.get("role_id"),
    )
    with tool_context(ctx):
        outcome = await execute_tool(action, payload)

    await record_audit(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        action=f"ai.{action}",
        target_type=action,
        payload={
            "params": payload,
            "result_kind": outcome.kind,
            "code": outcome.code,
            "error_type": outcome.error_type,
            "confirmation_source": "user_confirm",
        },
    )
    await db.commit()

    return ChatResponse(
        code=0 if outcome.ok else outcome.code or 400,
        msg="success" if outcome.ok else outcome.text,
        data={
            "action": action,
            "success": outcome.ok,
            "reply": outcome.text,
            "timestamp": datetime.now().isoformat(),
        },
    )


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    session_id: str = Query(default="default", pattern=SESSION_ID_PATTERN),
    agent_runtime: AgentRuntime = Depends(get_agent_runtime),
):
    messages = await agent_runtime.session.get_history(session_id)

    return HistoryResponse(
        data=[
            {
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
                "timestamp": msg.get("timestamp", ""),
            }
            for msg in messages[-50:]
        ]
    )


@router.delete("/history")
async def clear_history(
    session_id: str = Query(default="default", pattern=SESSION_ID_PATTERN),
    agent_runtime: AgentRuntime = Depends(get_agent_runtime),
):
    await agent_runtime.session.clear(session_id)
    return {"code": 0, "msg": "已清空对话历史"}


@router.get("/intents")
async def get_supported_intents(current_user: dict = Depends(get_current_user)):
    from app.ai.agent.intent import IntentRecognizer

    recognizer = IntentRecognizer()

    # 意图清单唯一事实源为 IntentRecognizer.INTENTS，通过 list_intents() 只读枚举
    intents = recognizer.list_intents()

    return {"code": 0, "data": intents}
