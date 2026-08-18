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

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import time

from app.ai.agent.runtime import AgentRuntime
from app.deps.auth import get_current_user, get_redis_client
from app.core.exceptions import DanceSaasException

router = APIRouter(prefix="/api/v1/ai", tags=["AI 智能助手"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = Field(default="default")


class ChatResponse(BaseModel):
    code: int = 0
    msg: str = "success"
    data: Optional[dict] = None


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
        user_id=current_user.get("user_id") if current_user else None
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    request: Request,
    agent_runtime: AgentRuntime = Depends(get_agent_runtime)
):
    start_time = time.time()
    
    try:
        response_text = await agent_runtime.chat(
            user_input=body.message,
            session_id=body.session_id
        )
        
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
                "latency_ms": latency_ms
            }
        )
        
    except DanceSaasException as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"code": 50001, "message": "AI 服务暂时不可用"}
        )


@router.get("/history", response_model=HistoryResponse)
async def get_history(
    session_id: str = "default",
    agent_runtime: AgentRuntime = Depends(get_agent_runtime)
):
    try:
        messages = await agent_runtime.session.get_history(session_id)
        
        return HistoryResponse(
            data=[
                {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "timestamp": msg.get("timestamp", "")
                }
                for msg in messages[-50:]
            ]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="获取历史记录失败")


@router.delete("/history")
async def clear_history(
    session_id: str = "default",
    agent_runtime: AgentRuntime = Depends(get_agent_runtime)
):
    try:
        await agent_runtime.session.clear(session_id)
        return {"code": 0, "msg": "已清空对话历史"}
    except Exception as e:
        raise HTTPException(status_code=500, detail="清空失败")


@router.get("/intents")
async def get_supported_intents():
    from app.ai.agent.intent import IntentRecognizer
    
    recognizer = IntentRecognizer()
    
    intents = []
    for intent_name, intent_config in recognizer.intents.items():
        intents.append({
            "intent": intent_name,
            "description": intent_config.get("description", ""),
            "examples": intent_config.get("examples", [])
        })
    
    return {"code": 0, "data": intents}