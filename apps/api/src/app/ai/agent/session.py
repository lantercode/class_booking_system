"""
会话管理
职责：Redis 读写对话历史，支持多轮上下文

企业级特性：
  - user_id + session_id 双层隔离，物理防止跨用户会话泄露
  - 对话历史自动截断（max_history * 2 条）
  - 中间状态 TTL 10 分钟自动过期
"""

import json
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """
    会话管理器（用户级隔离版）

    Redis Key 命名规范:
      ai:session:{user_id}:{session_id}  — 对话历史
      ai:state:{user_id}:{session_id}    — 中间状态（多轮对话暂存）
      ai:lock:{user_id}:{session_id}      — 并发锁

    为什么要 user_id + session_id？
      1. 防止跨用户会话串台（同一个 session_id 被不同用户使用）
      2. 防止越权读取（猜到别人的 session_id 没用，key 里还有 user_id）
      3. 一个用户可以有多个会话（比如"约课会话"、"查课会话"），互不干扰
    """

    def __init__(self, redis_client=None, user_id: int = None):
        self.redis = redis_client
        self.user_id = user_id
        self.max_history = 10
        self.ttl = 3600  # 对话历史 1 小时过期

    def _session_scope_key(self, session_id: str) -> str:
        """
        生成带 user_id 的 Redis key

        格式: ai:session:{user_id}:{session_id}
        如果 user_id 为 None（未登录），退化为 ai:session:anon:{session_id}
        """
        user_part = f"user_{self.user_id}" if self.user_id else "anon"
        return f"ai:session:{user_part}:{session_id}"

    def _state_scope_key(self, session_id: str) -> str:
        """生成带 user_id 的状态 key"""
        user_part = f"user_{self.user_id}" if self.user_id else "anon"
        return f"ai:state:{user_part}:{session_id}"

    def _lock_scope_key(self, session_id: str) -> str:
        """生成带 user_id 的锁 key"""
        user_part = f"user_{self.user_id}" if self.user_id else "anon"
        return f"ai:lock:{user_part}:{session_id}"

    async def get_history(self, session_id: str) -> list[dict]:
        """获取会话历史"""
        if not self.redis:
            return []

        try:
            raw = await self.redis.get(self._session_scope_key(session_id))
            if raw:
                return json.loads(raw)
        except Exception:
            logger.error(f"[SessionManager] 获取历史失败: session={session_id}")
        return []

    async def add_message(self, session_id: str, role: str, content: str):
        """添加一条消息到会话历史"""
        if not self.redis:
            return

        try:
            history = await self.get_history(session_id)
            history.append({"role": role, "content": content})

            max_messages = self.max_history * 2
            if len(history) > max_messages:
                history = history[-max_messages:]

            await self.redis.set(
                self._session_scope_key(session_id),
                json.dumps(history, ensure_ascii=False),
                ex=self.ttl,
            )
        except Exception:
            logger.error(f"[SessionManager] 添加消息失败: session={session_id}")

    async def clear(self, session_id: str):
        """清空会话历史"""
        if self.redis:
            try:
                await self.redis.delete(self._session_scope_key(session_id))
            except Exception:
                logger.error(f"[SessionManager] 清空历史失败: session={session_id}")

    async def get_context(self, session_id: str, last_n: int = 4) -> str:
        """获取最近 N 条消息作为文本上下文"""
        history = await self.get_history(session_id)
        recent = history[-last_n:] if len(history) > last_n else history

        lines = []
        for msg in recent:
            role_label = "用户" if msg["role"] == "user" else "助手"
            lines.append(f"{role_label}: {msg['content']}")
        return "\n".join(lines)

    async def set_state(self, session_id: str, state: dict):
        """
        存储对话中间状态（如用户正在选择哪个排期）
        TTL=600秒，10分钟后自动过期
        """
        if not self.redis:
            return

        try:
            await self.redis.set(
                self._state_scope_key(session_id),
                json.dumps(state, ensure_ascii=False),
                ex=600,
            )
        except Exception:
            logger.error(f"[SessionManager] 设置状态失败: session={session_id}")

    async def get_state(self, session_id: str) -> dict:
        """获取当前对话的中间状态"""
        if not self.redis:
            return {}

        try:
            raw = await self.redis.get(self._state_scope_key(session_id))
            if raw:
                return json.loads(raw)
        except Exception:
            logger.error(f"[SessionManager] 获取状态失败: session={session_id}")
        return {}

    async def clear_state(self, session_id: str):
        """清除对话状态"""
        if self.redis:
            try:
                await self.redis.delete(self._state_scope_key(session_id))
            except Exception:
                logger.error(f"[SessionManager] 清除状态失败: session={session_id}")
