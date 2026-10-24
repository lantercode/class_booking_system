"""
F1.3 异常处理器单元测试

测试内容：
- unhandled_exception_handler 返回 500 统一信封、不含原始异常消息、含 request_id
- Settings.APP_DEBUG 默认值为 False

运行方式：
    cd apps/api
    uv run pytest tests/test_exception_handlers.py -v
"""

import json

import pytest
from starlette.requests import Request

from app.core.config import Settings
from app.middleware.error_handler import unhandled_exception_handler


def _make_request(path: str = "/api/v1/test") -> Request:
    """构造一个最小可用的 starlette Request 用于直调 handler。"""
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
        "scheme": "http",
    }
    return Request(scope)


class TestUnhandledExceptionHandler:
    """通用兜底异常处理器测试。"""

    @pytest.mark.asyncio
    async def test_returns_500_status_code(self):
        request = _make_request()
        exc = ValueError("sensitive internal detail: database connection refused")

        response = await unhandled_exception_handler(request, exc)

        assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_returns_unified_envelope(self):
        request = _make_request()
        exc = RuntimeError("boom")

        response = await unhandled_exception_handler(request, exc)
        body = json.loads(response.body)

        # 统一信封字段
        assert body.get("code") == 500
        assert body.get("data") is None
        assert body.get("msg") == "服务暂时不可用，请稍后重试"
        assert isinstance(body.get("request_id"), str)
        assert body["request_id"].startswith("req_")

    @pytest.mark.asyncio
    async def test_does_not_leak_original_exception_message(self):
        """原始异常消息不得出现在响应体中。"""
        secret_detail = "db_password=super_secret_token_123"
        request = _make_request()
        exc = Exception(secret_detail)

        response = await unhandled_exception_handler(request, exc)
        body = json.loads(response.body)

        assert secret_detail not in response.body.decode()
        assert secret_detail not in body.get("msg", "")

    @pytest.mark.asyncio
    async def test_contains_request_id(self):
        request = _make_request("/api/v1/ai/chat")
        exc = KeyError("missing_key")

        response = await unhandled_exception_handler(request, exc)
        body = json.loads(response.body)

        assert "request_id" in body
        assert len(body["request_id"]) > 0

    @pytest.mark.asyncio
    async def test_content_type_is_json(self):
        request = _make_request()
        exc = AssertionError("should not appear")

        response = await unhandled_exception_handler(request, exc)

        assert response.media_type == "application/json"


class TestAppDebugDefault:
    """APP_DEBUG 默认值测试。"""

    def test_app_debug_default_is_false(self):
        """Settings.APP_DEBUG 字段默认值必须为 False。"""
        assert Settings.model_fields["APP_DEBUG"].default is False

    def test_app_debug_type_is_bool(self):
        """APP_DEBUG 字段类型为 bool。"""
        field = Settings.model_fields["APP_DEBUG"]
        assert field.annotation is bool
