"""
会话管理
职责：Redis 读写对话历史，支持多轮上下文
"""

import json
from typing import List, Dict, Optional


class SessionManager:
    """
    会话管理器

    使用 Redis 存储对话历史，支持多轮上下文
    max_history: 保留最近 N 轮对话（1 轮 = user + assistant 各 1 条）
    """

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self.max_history = 10
        self.ttl = 3600  # 会话过期时间 1 小时

    def _key(self, session_id: str) -> str:
        return f"ai:session:{session_id}"

    async def get_history(self, session_id: str) -> List[Dict]:
        """
        获取会话历史，供 LLM 作为上下文使用

        Returns:
            [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        """
        if not self.redis:
            return []

        try:
            raw = await self.redis.get(self._key(session_id))
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return []

    async def add_message(self, session_id: str, role: str, content: str):
        """
        添加一条消息到会话历史
        """
        if not self.redis:
            return

        try:
            history = await self.get_history(session_id)
            history.append({"role": role, "content": content})

            max_messages = self.max_history * 2
            if len(history) > max_messages:
                history = history[-max_messages:]

            await self.redis.set(
                self._key(session_id),
                json.dumps(history, ensure_ascii=False),
                ex=self.ttl,
            )
        except Exception:
            pass

    async def clear(self, session_id: str):
        """清空会话历史"""
        if self.redis:
            try:
                await self.redis.delete(self._key(session_id))
            except Exception:
                pass

    async def get_context(self, session_id: str, last_n: int = 4) -> str:
        """
        获取最近 N 条消息作为文本上下文

        用于给 LLM 提供对话背景
        """
        history = await self.get_history(session_id)
        recent = history[-last_n:] if len(history) > last_n else history

        lines = []
        for msg in recent:
            role_label = "用户" if msg["role"] == "user" else "助手"
            lines.append(f"{role_label}: {msg['content']}")
        return "\n".join(lines)


    def _state_key(self, session_id: str) -> str:
        return f"ai:state:{session_id}"

    async def set_state(self, session_id: str, state: dict):
        """
        存储对话中间状态（如用户正在选择哪个排期）
        
        用途：多轮对话时暂存上下文，例如：
          - 用户说"帮我约瑜伽课" → 查到3个排期 → 存到这里 → 等用户选择
          - TTL=600秒，10分钟后自动过期（防止僵尸状态）
        """
        if not self.redis:
            return

        try:
            await self.redis.set(
                self._state_key(session_id),
                json.dumps(state, ensure_ascii=False),
                ex=600,
            )
        except Exception:
            pass

    async def get_state(self, session_id: str) -> dict:
        """
        获取当前对话的中间状态
        
        Returns:
            dict: 状态字典，如 {"action": "selecting_schedule", "schedules": [...]}
                  如果没有状态或已过期，返回 {}
        """
        if not self.redis:
            return {}

        try:
            raw = await self.redis.get(self._state_key(session_id))
            if raw:
                return json.loads(raw)
        except Exception:
            pass
        return {}

    async def clear_state(self, session_id: str):
        """
        清除对话状态（用户完成选择或取消操作后调用）
        """
        if self.redis:
            try:
                await self.redis.delete(self._state_key(session_id))
            except Exception:
                pass