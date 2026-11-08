"""AI Agent 接入前安全收口测试（不依赖真实 DB / Redis / 网络）.

覆盖：
- P0-2 信任边界：execute_tool 不接受身份参数；身份只能来自可信 ContextVar；
  业务入参里的 user_id / tenant_id 会被忽略；跨租户显式身份被拒绝。
- P0-3 限流：仅 /api/v1/ai/chat 生效、按登录用户计数、其他业务 API 不受影响。
- P0-4 session_id：长度 / 字符集校验，且会话 key 带 user_id 前缀。
- P0-5 会话隔离：不同用户、不同 session_id 互不可见。
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai import mcp_server
from app.ai.agent.session import SessionManager
from app.ai.mcp_server import (
    TOOL_SPECS,
    ToolContext,
    ToolOutcome,
    execute_tool,
    tool_context,
)
from app.core.exceptions import BusinessException
from app.core.security import create_access_token
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.modules.ai.router import ChatRequest, get_agent_runtime
from app.modules.ai.router import router as ai_router


class FakeRedis:
    """内存版 Redis，仅实现 SessionManager 使用的 get/set/delete。"""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    async def delete(self, key):
        self.store.pop(key, None)


# ============================================================
# P0-2 信任边界
# ============================================================


@pytest.mark.asyncio
async def test_execute_tool_without_trusted_context_is_rejected():
    """未由宿主绑定 ToolContext 时，任何 Tool 都不得执行。"""
    outcome = await execute_tool("get_my_balance", {})

    assert outcome.kind == "business_error"
    assert outcome.code == 401
    assert outcome.error_type == "AuthenticationError"


@pytest.mark.asyncio
async def test_execute_tool_rejects_forged_context_argument():
    """签名不再接受 context/user_id/tenant_id 参数，调用方无法按请求伪造身份。"""
    with pytest.raises(TypeError):
        await execute_tool("get_my_balance", {}, ToolContext(user_id=999, tenant_id=888))


@pytest.mark.asyncio
async def test_identity_arguments_cannot_override_trusted_context(monkeypatch):
    """模型/前端即使把 user_id / tenant_id 塞进 arguments，也只会使用可信上下文。"""
    captured: dict = {}

    async def fake_handler(*, user_id=None, tenant_id=None):
        captured.update({"user_id": user_id, "tenant_id": tenant_id})
        return ToolOutcome("success", "ok")

    monkeypatch.setattr(mcp_server, "get_my_balance", fake_handler)

    with tool_context(ToolContext(user_id=7, tenant_id=3)):
        outcome = await execute_tool(
            "get_my_balance",
            {"user_id": 999, "tenant_id": 888},
        )

    assert outcome.ok is True
    assert captured == {"user_id": 7, "tenant_id": 3}
    assert "user_id" not in TOOL_SPECS["get_my_balance"].input_fields
    assert "tenant_id" not in TOOL_SPECS["get_my_balance"].input_fields


@pytest.mark.asyncio
async def test_execute_tool_rejects_polluted_request_context(monkeypatch):
    """ToolContext 与请求级 ContextVar 不一致时拒绝，避免静默覆盖成他人身份。"""
    calls: list[str] = []

    async def fake_handler(*, user_id=None, tenant_id=None):
        calls.append("called")
        return ToolOutcome("success", "ok")

    monkeypatch.setattr(mcp_server, "get_my_balance", fake_handler)

    with tool_context(ToolContext(user_id=1, tenant_id=1)):
        token = mcp_server._tenant_id_var.set(2)
        try:
            outcome = await execute_tool("get_my_balance", {})
        finally:
            mcp_server._tenant_id_var.reset(token)

    assert outcome.kind == "business_error"
    assert outcome.code == 403
    assert outcome.error_type == "TenantMismatch"
    assert calls == []


@pytest.mark.asyncio
async def test_explicit_identity_must_match_trusted_context():
    """Tool 内部兼容旧调用方时，显式身份必须与可信上下文一致（跨租户直接拒绝）。"""
    with tool_context(ToolContext(user_id=1, tenant_id=1)):
        with pytest.raises(BusinessException) as tenant_exc:
            await mcp_server.query_schedules_impl(tenant_id=2)
        assert tenant_exc.value.code == 403

        with pytest.raises(BusinessException) as user_exc:
            await mcp_server.query_schedules_impl(user_id=2)
        assert user_exc.value.code == 403


# ============================================================
# P0-5 会话 / 数据隔离
# ============================================================


@pytest.mark.asyncio
async def test_session_history_is_isolated_between_users():
    """相同 session_id 在不同用户下必须互不可见（key 带 user_id 前缀）。"""
    redis = FakeRedis()
    alice = SessionManager(redis, user_id=1)
    bob = SessionManager(redis, user_id=2)

    await alice.add_message("default", "user", "alice-secret")
    await alice.set_state("default", {"action": "selecting_schedule"})

    assert await bob.get_history("default") == []
    assert await bob.get_state("default") == {}

    history = await alice.get_history("default")
    assert len(history) == 1
    assert history[0]["content"] == "alice-secret"
    assert "user_1" in alice._session_scope_key("default")
    assert "user_2" in bob._session_scope_key("default")


@pytest.mark.asyncio
async def test_session_scoped_by_session_id():
    """同一用户的不同 session_id 同样隔离。"""
    redis = FakeRedis()
    manager = SessionManager(redis, user_id=1)

    await manager.add_message("booking", "user", "约课会话")
    await manager.add_message("course", "user", "查课会话")

    assert (await manager.get_history("booking"))[0]["content"] == "约课会话"
    assert (await manager.get_history("course"))[0]["content"] == "查课会话"


# ============================================================
# P0-4 session_id 校验
# ============================================================


@pytest.mark.parametrize(
    "session_id",
    [
        "",
        "a" * 65,
        "abc/def",
        "abc def",
        "中文会话",
        "abc.def",
        "abc:def",
    ],
)
def test_chat_request_rejects_invalid_session_id(session_id):
    with pytest.raises(ValidationError):
        ChatRequest(message="hi", session_id=session_id)


@pytest.mark.parametrize(
    "session_id",
    ["default", "a", "chat-2026_11_07", "a" * 64],
)
def test_chat_request_accepts_valid_session_id(session_id):
    body = ChatRequest(message="hi", session_id=session_id)
    assert body.session_id == session_id


class _DummyRuntime:
    class _Session:
        async def get_history(self, session_id):
            return []

        async def get_state(self, session_id):
            return {}

        async def clear(self, session_id):
            return None

    def __init__(self):
        self.session = self._Session()

    async def chat(self, user_input: str, session_id: str) -> str:
        return f"echo:{user_input}:{session_id}"


def _build_ai_test_app() -> TestClient:
    app = FastAPI()
    app.include_router(ai_router)
    app.dependency_overrides[get_agent_runtime] = lambda: _DummyRuntime()
    return TestClient(app)


@pytest.mark.parametrize(
    "method,path",
    [("get", "/api/v1/ai/history"), ("delete", "/api/v1/ai/history")],
)
def test_history_rejects_invalid_session_id(method, path):
    client = _build_ai_test_app()
    response = getattr(client, method)(path, params={"session_id": "a" * 65})
    assert response.status_code == 422


def test_chat_endpoint_rejects_invalid_session_id():
    client = _build_ai_test_app()
    response = client.post(
        "/api/v1/ai/chat",
        json={"message": "hi", "session_id": "abc/def"},
    )
    assert response.status_code == 422


def test_chat_endpoint_accepts_valid_session_id():
    client = _build_ai_test_app()
    response = client.post(
        "/api/v1/ai/chat",
        json={"message": "hi", "session_id": "chat-2026_11_07"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["session_id"] == "chat-2026_11_07"


# ============================================================
# P0-3 AI 接口限流
# ============================================================


def _build_rate_limit_app(limit: int = 2, window: int = 60) -> TestClient:
    app = FastAPI()

    @app.post("/api/v1/ai/chat")
    async def chat():  # pragma: no cover - 仅用于验证限流
        return {"code": 0, "msg": "success", "data": None}

    @app.get("/api/v1/bookings")
    async def bookings():  # pragma: no cover - 仅用于验证不受影响
        return {"code": 0, "msg": "success", "data": []}

    app.add_middleware(
        RateLimiterMiddleware,
        limit=limit,
        window=window,
        path_limits={"/api/v1/ai/chat": (limit, window)},
        user_key_paths=("/api/v1/ai/chat",),
        only_path_limits=True,
    )
    return TestClient(app)


def test_rate_limit_returns_429_envelope_after_threshold():
    client = _build_rate_limit_app(limit=2)
    payload = {"message": "hi"}

    first = client.post("/api/v1/ai/chat", json=payload)
    second = client.post("/api/v1/ai/chat", json=payload)
    third = client.post("/api/v1/ai/chat", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    body = third.json()
    assert body["code"] == 429
    assert body["msg"] == "请求过于频繁，请稍后再试"
    assert third.headers["X-RateLimit-Limit"] == "2"
    assert third.headers["Retry-After"]


def test_rate_limit_is_per_user_not_shared():
    client = _build_rate_limit_app(limit=2)
    token_a = create_access_token({"user_id": 1, "tenant_id": 1})
    token_b = create_access_token({"user_id": 2, "tenant_id": 1})

    for _ in range(2):
        assert (
            client.post(
                "/api/v1/ai/chat",
                json={"message": "hi"},
                headers={"Authorization": f"Bearer {token_a}"},
            ).status_code
            == 200
        )

    blocked = client.post(
        "/api/v1/ai/chat",
        json={"message": "hi"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert blocked.status_code == 429

    # 另一个用户不受影响
    assert (
        client.post(
            "/api/v1/ai/chat",
            json={"message": "hi"},
            headers={"Authorization": f"Bearer {token_b}"},
        ).status_code
        == 200
    )


def test_rate_limit_does_not_affect_other_business_api():
    client = _build_rate_limit_app(limit=2)

    responses = [client.get("/api/v1/bookings") for _ in range(5)]

    assert all(response.status_code == 200 for response in responses)
    assert all(response.json()["code"] == 0 for response in responses)
