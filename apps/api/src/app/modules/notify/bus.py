"""实时推送总线（阶段 4）。

**只推信号，不推业务数据**：事件体仅含 ``type / entity_id / version``，
前端收到后自行按 type 拉取详情，避免推送体与权限模型耦合。

投递路径：
- 发布：业务提交后 -> Redis channel ``notify:events``；
- 分发：每个实例的监听任务收到消息 -> 进程内订阅队列 -> SSE / WebSocket 连接；
- ``user_id = 0`` 表示租户内广播（管理端），其余为定向用户（学员端）。

Redis 不可用时降级为进程内广播（仅单实例有效），并记录告警。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)

CHANNEL = "notify:events"


class NotifyBus:
    """进程内订阅表 + 连接配额。"""

    def __init__(
        self, max_connections_per_user: int = 3, max_events_per_second: int = 20
    ) -> None:
        self._subs: dict[tuple[int, int], set[asyncio.Queue]] = defaultdict(set)
        self._counts: dict[tuple[int, int], int] = defaultdict(int)
        self._windows: dict[tuple[int, int], tuple[float, int]] = {}
        self.max_connections_per_user = max_connections_per_user
        self.max_events_per_second = max_events_per_second

    # ---------------- 连接配额（阶段 4.6） ----------------

    def acquire(self, tenant_id: int, user_id: int) -> bool:
        key = (tenant_id, user_id)
        if self._counts[key] >= self.max_connections_per_user:
            return False
        self._counts[key] += 1
        return True

    def release(self, tenant_id: int, user_id: int) -> None:
        key = (tenant_id, user_id)
        if self._counts.get(key, 0) > 0:
            self._counts[key] -= 1
            if self._counts[key] == 0:
                self._counts.pop(key, None)
                # 最后一个连接断开后清理该用户的速率窗口，避免字典无限增长
                self._windows.pop(key, None)

    # ---------------- 消息速率限制（阶段 4.6） ----------------

    def _allow_event(self, key: tuple[int, int]) -> bool:
        """按 (tenant_id, user_id) 做 1 秒滑动窗口限流；超限返回 False。

        信号可被 HTTP 补齐，因此超限选择丢弃而不是断开连接。
        """
        limit = self.max_events_per_second
        if limit <= 0:
            return True
        now = time.monotonic()
        window = self._windows.get(key)
        if window is None or now - window[0] >= 1.0:
            self._windows[key] = (now, 1)
            return True
        if window[1] >= limit:
            return False
        self._windows[key] = (window[0], window[1] + 1)
        return True

    # ---------------- 订阅/分发 ----------------

    def subscribe(self, tenant_id: int, user_id: int) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._subs[(tenant_id, user_id)].add(queue)
        return queue

    def unsubscribe(self, tenant_id: int, user_id: int, queue: asyncio.Queue) -> None:
        subs = self._subs.get((tenant_id, user_id))
        if subs:
            subs.discard(queue)
            if not subs:
                self._subs.pop((tenant_id, user_id), None)

    async def dispatch_local(
        self, tenant_id: int, user_id: int, event: dict[str, Any]
    ) -> None:
        """投递到本实例的连接；user_id=0 时广播给该租户全部连接。"""
        if not self._allow_event((tenant_id, user_id)):
            # 丢弃信号而非断开：前端重连/下次事件可凭 HTTP 补齐
            logger.debug(
                "[notify] 事件速率超限，丢弃信号 tenant=%s user=%s", tenant_id, user_id
            )
            return

        queues: list[asyncio.Queue] = []
        if user_id == 0:
            for (tid, _uid), subs in self._subs.items():
                if tid == tenant_id:
                    queues.extend(subs)
        else:
            queues.extend(self._subs.get((tenant_id, user_id), ()))

        for queue in queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # 客户端消费过慢：丢弃本次信号（前端可凭 HTTP 补齐）
                logger.warning(
                    "[notify] 队列已满，丢弃事件 tenant=%s user=%s", tenant_id, user_id
                )


bus = NotifyBus()


# ---------------------------------------------------------------------------
# Redis 发布 / 订阅
# ---------------------------------------------------------------------------

_pubsub = None
_listener_task: asyncio.Task | None = None


async def publish_change(
    *,
    tenant_id: int,
    user_id: int,
    type: str,
    entity_id: int,
    version: int = 1,
) -> None:
    """业务提交后发布状态变更信号；失败只告警，不影响主流程。"""
    event = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "type": type,
        "entity_id": entity_id,
        "version": version,
    }
    payload = json.dumps(event, ensure_ascii=False)
    try:
        from app.deps.auth import get_redis_client

        redis = await get_redis_client()
        await redis.publish(CHANNEL, payload)
    except Exception as e:
        logger.warning(
            "[notify] Redis 发布失败，降级为进程内广播（多实例不可靠）: %s", e
        )
        await bus.dispatch_local(tenant_id, user_id, _client_event(event))


def _client_event(event: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": event["type"],
        "entity_id": event["entity_id"],
        "version": event["version"],
    }


async def _listen() -> None:
    assert _pubsub is not None
    async for message in _pubsub.listen():
        if message.get("type") != "message":
            continue
        try:
            event = json.loads(message["data"])
            await bus.dispatch_local(
                int(event["tenant_id"]),
                int(event["user_id"]),
                _client_event(event),
            )
        except Exception:
            logger.exception("[notify] 事件解析/分发失败")


async def start_listener() -> None:
    """启动 Redis 订阅（lifespan 调用，Redis 必须可用）。"""
    global _pubsub, _listener_task
    from app.deps.auth import get_redis_client

    redis = await get_redis_client()
    _pubsub = redis.pubsub()
    await _pubsub.subscribe(CHANNEL)
    _listener_task = asyncio.create_task(_listen(), name="notify-redis-listener")
    logger.info("[notify] Redis 订阅已启动 channel=%s", CHANNEL)


async def stop_listener() -> None:
    global _pubsub, _listener_task
    if _listener_task:
        _listener_task.cancel()
        try:
            await _listener_task
        except (asyncio.CancelledError, Exception):
            pass
        _listener_task = None
    if _pubsub:
        try:
            await _pubsub.unsubscribe(CHANNEL)
            await _pubsub.close()
        except Exception:
            logger.exception("[notify] 关闭 Redis 订阅失败")
        _pubsub = None
