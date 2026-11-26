"""实时推送总线单测（阶段 4）。

覆盖：连接配额、定向/广播分发、队列满丢弃、Redis 发布失败降级。
不依赖真实 DB / Redis。
"""

from __future__ import annotations

from app.modules.notify import bus as bus_module
from app.modules.notify.bus import NotifyBus


def test_acquire_respects_limit():
    bus = NotifyBus(max_connections_per_user=2)
    assert bus.acquire(1, 10) is True
    assert bus.acquire(1, 10) is True
    assert bus.acquire(1, 10) is False  # 超限
    assert bus.acquire(1, 11) is True  # 其他用户不受影响


def test_release_frees_slot():
    bus = NotifyBus(max_connections_per_user=1)
    assert bus.acquire(1, 10) is True
    assert bus.acquire(1, 10) is False
    bus.release(1, 10)
    assert bus.acquire(1, 10) is True


def test_release_never_goes_negative():
    bus = NotifyBus(max_connections_per_user=1)
    bus.release(1, 10)
    bus.release(1, 10)
    # 释放次数多于获取次数后，仍可正常获取
    assert bus.acquire(1, 10) is True


async def test_dispatch_directed_only_to_target_user():
    bus = NotifyBus()
    q_target = bus.subscribe(1, 10)
    q_other = bus.subscribe(1, 11)

    event = {"type": "booking.created", "entity_id": 88, "version": 1}
    await bus.dispatch_local(1, 10, event)

    assert q_target.get_nowait() == event
    assert q_other.empty()


async def test_dispatch_user_zero_broadcasts_within_tenant_only():
    bus = NotifyBus()
    q_a = bus.subscribe(1, 10)
    q_b = bus.subscribe(1, 11)
    q_other_tenant = bus.subscribe(2, 10)

    event = {"type": "schedule.cancelled", "entity_id": 5, "version": 1}
    await bus.dispatch_local(1, 0, event)

    assert q_a.get_nowait() == event
    assert q_b.get_nowait() == event
    assert q_other_tenant.empty()


async def test_dispatch_drops_when_queue_full():
    bus = NotifyBus()
    queue = bus.subscribe(1, 10)
    # 把队列填满（maxsize=100）
    for i in range(100):
        queue.put_nowait({"type": "x", "entity_id": i, "version": 1})

    # 不应抛异常，且不阻塞
    await bus.dispatch_local(1, 10, {"type": "overflow", "entity_id": 1, "version": 1})
    assert queue.qsize() == 100


async def test_publish_change_falls_back_to_local_on_redis_error(monkeypatch):
    fake_bus = NotifyBus()
    monkeypatch.setattr(bus_module, "bus", fake_bus)

    async def _broken_redis():
        raise RuntimeError("redis down")

    monkeypatch.setattr("app.deps.auth.get_redis_client", _broken_redis)

    queue = fake_bus.subscribe(1, 10)
    await bus_module.publish_change(
        tenant_id=1, user_id=10, type="booking.created", entity_id=99
    )

    event = queue.get_nowait()
    # 只推信号，不透传内部字段
    assert event == {"type": "booking.created", "entity_id": 99, "version": 1}


async def test_publish_change_via_redis(monkeypatch):
    published: list[tuple[str, str]] = []

    class _FakeRedis:
        async def publish(self, channel, payload):
            published.append((channel, payload))
            return 1

    async def _fake_redis():
        return _FakeRedis()

    monkeypatch.setattr("app.deps.auth.get_redis_client", _fake_redis)

    await bus_module.publish_change(
        tenant_id=1, user_id=0, type="schedule.cancelled", entity_id=7
    )

    assert len(published) == 1
    channel, payload = published[0]
    assert channel == bus_module.CHANNEL
    assert '"type": "schedule.cancelled"' in payload
    assert '"entity_id": 7' in payload


async def test_dispatch_respects_event_rate_limit():
    bus = NotifyBus(max_events_per_second=2)
    queue = bus.subscribe(1, 10)

    for i in range(3):
        await bus.dispatch_local(1, 10, {"type": "t", "entity_id": i, "version": 1})

    # 1 秒窗口内只放行 2 条，第 3 条被丢弃且不阻塞
    assert queue.qsize() == 2


async def test_event_rate_limit_is_per_user():
    bus = NotifyBus(max_events_per_second=1)
    q_a = bus.subscribe(1, 10)
    q_b = bus.subscribe(1, 11)

    await bus.dispatch_local(1, 10, {"type": "t", "entity_id": 1, "version": 1})
    await bus.dispatch_local(1, 10, {"type": "t", "entity_id": 2, "version": 1})
    await bus.dispatch_local(1, 11, {"type": "t", "entity_id": 3, "version": 1})

    assert q_a.qsize() == 1
    assert q_b.qsize() == 1


async def test_release_clears_rate_window():
    bus = NotifyBus(max_connections_per_user=1, max_events_per_second=1)
    assert bus.acquire(1, 10) is True
    bus.subscribe(1, 10)
    await bus.dispatch_local(1, 10, {"type": "t", "entity_id": 1, "version": 1})
    await bus.dispatch_local(1, 10, {"type": "t", "entity_id": 2, "version": 1})

    bus.release(1, 10)
    assert (1, 10) not in bus._windows


def test_client_event_strips_internal_fields():
    out = bus_module._client_event(
        {
            "tenant_id": 1,
            "user_id": 10,
            "type": "t",
            "entity_id": 2,
            "version": 3,
        }
    )
    assert out == {"type": "t", "entity_id": 2, "version": 3}


async def test_unsubscribe_removes_empty_key():
    bus = NotifyBus()
    queue = bus.subscribe(1, 10)
    bus.unsubscribe(1, 10, queue)
    assert (1, 10) not in bus._subs

    # 退订后不再收到事件
    await bus.dispatch_local(1, 10, {"type": "t", "entity_id": 1, "version": 1})
    assert queue.empty()
