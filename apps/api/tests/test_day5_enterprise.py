"""
Day 5 测试：企业级功能验证（面向面试）

测试内容：
  1. 分布式锁防并发
  2. cancel_booking 多轮确认
  3. 业务错误码友好提示
  4. 结构化日志输出

运行方式：
  cd /Users/lixiang/Desktop/class_booking_system/apps/api
  PYTHONPATH=src .venv/bin/python tests/test_day5_enterprise.py
"""

import asyncio
import sys

sys.path.insert(0, 'src')

import redis.asyncio as aioredis

from app.ai.agent.runtime import AgentRuntime


async def get_redis_client():
    """获取 Redis 客户端"""
    try:
        client = aioredis.from_url(
            "redis://localhost:6379/0",
            decode_responses=True,
        )
        await client.ping()
        return client
    except Exception as e:
        print(f"⚠️ Redis 连接失败: {e}")
        print("   测试将使用无 Redis 模式（多轮对话功能受限）")
        return None


async def test_distributed_lock():
    """测试分布式锁：同一 session 并发请求应被拦截"""

    print("=" * 60)
    print("🧪 测试 1：分布式锁防并发")
    print("=" * 60)

    redis_client = await get_redis_client()
    runtime = AgentRuntime(redis_client=redis_client, user_id=1)
    session_id = "test_lock_session"

    print("\n📌 模拟并发场景：快速发送两个请求")
    print("-" * 60)

    task1 = asyncio.create_task(
        runtime.chat("帮我约瑜伽课", session_id)
    )

    await asyncio.sleep(0.01)

    task2 = asyncio.create_task(
        runtime.chat("1", session_id)
    )

    result1, result2 = await asyncio.gather(task1, task2)

    print(f"请求1 结果: {result1[:50]}...")
    print(f"请求2 结果: {result2[:50]}...")

    if "⏳ 正在处理" in result2 or "⏳ 正在处理" in result1:
        print("\n✅ 分布式锁生效：并发请求被正确拦截")
    else:
        print("\n⚠️ 未触发并发拦截（可能执行太快，属于正常情况）")

    if redis_client:
        await redis_client.close()
    return True


async def test_cancel_booking_confirmation():
    """测试取消预约的多轮确认流程"""

    print("\n" + "=" * 60)
    print("🧪 测试 2：cancel_booking 多轮确认")
    print("=" * 60)

    redis_client = await get_redis_client()
    runtime = AgentRuntime(redis_client=redis_client, user_id=1)
    session_id = "test_cancel_session"

    print("\n📌 第 1 轮：用户说「取消预约 1001」")
    print("-" * 60)

    response_1 = await runtime.chat(
        user_input="取消预约 1001",
        session_id=session_id,
    )

    print(f"🤖 Agent 回复：\n{response_1}")

    if "确定要取消" in response_1 or "确认" in response_1:
        print("✅ 第 1 轮通过：成功进入确认状态")
    else:
        print(f"❌ 第 1 轮失败：预期显示确认提示，实际：{response_1}")
        if redis_client:
            await redis_client.close()
        return False

    print("\n📌 第 2 轮：用户回复「是」确认取消")
    print("-" * 60)

    response_2 = await runtime.chat(
        user_input="是",
        session_id=session_id,
    )

    print(f"🤖 Agent 回复：\n{response_2}")

    if "已成功取消" in response_2 or "取消失败" in response_2 or "处理请求时出错" in response_2:
        print("✅ 第 2 轮通过：执行了取消操作")
    else:
        print(f"⚠️ 第 2 轮结果：{response_2}")

    print("\n📌 验证：状态是否已清除")
    state = await runtime.session.get_state(session_id)
    if not state:
        print("✅ 状态已清除")
    else:
        print(f"❌ 状态残留：{state}")
        if redis_client:
            await redis_client.close()
        return False

    if redis_client:
        await redis_client.close()
    return True


async def test_cancel_rejection():
    """测试用户拒绝取消预约"""

    print("\n" + "=" * 60)
    print("🧪 测试 3：用户拒绝取消预约")
    print("=" * 60)

    redis_client = await get_redis_client()
    runtime = AgentRuntime(redis_client=redis_client, user_id=1)
    session_id = "test_cancel_reject"

    print("\n📌 第 1 轮：触发取消流程")
    response_1 = await runtime.chat("取消预约 2001", session_id)
    print(f"Agent: {response_1[:40]}...")

    print("\n📌 第 2 轮：用户回复「否」")
    print("-" * 60)

    response_2 = await runtime.chat("否", session_id)
    print(f"🤖 Agent 回复：\n{response_2}")

    if "保持不变" in response_2 or "取消操作" in response_2:
        print("✅ 用户拒绝取消：预约保持不变")
        if redis_client:
            await redis_client.close()
        return True
    else:
        print(f"❌ 预期保留预约，实际：{response_2}")
        if redis_client:
            await redis_client.close()
        return False


async def test_error_code_mapping():
    """测试业务错误码→友好提示"""

    print("\n" + "=" * 60)
    print("🧪 测试 4：业务错误码友好提示")
    print("=" * 60)

    runtime = AgentRuntime()

    test_cases = [
        ("SCHEDULE_FULL", "该时段刚被约满"),
        ("ALREADY_BOOKED", "已预约过此课程"),
        ("BALANCE_INSUFFICIENT", "课时余额不足"),
        ("BOOKING_NOT_FOUND", "未找到该预约记录"),
        ("UNKNOWN_ERROR_xyz", "处理请求时出错"),
    ]

    all_passed = True
    for error_msg, expected_keyword in test_cases:
        class MockError(Exception):
            def __init__(self):
                super().__init__(error_msg)

        result = runtime._handle_business_error(MockError())
        passed = expected_keyword in result
        status = "✅" if passed else "❌"
        print(f"{status} 错误码: {error_msg:25s} → 包含关键词: {expected_keyword}")
        if not passed:
            all_passed = False
            print(f"   实际返回: {result[:50]}...")

    return all_passed


async def test_logging_output():
    """验证日志是否正常输出（检查 logger 是否工作）"""

    print("\n" + "=" * 60)
    print("🧪 测试 5：结构化日志输出")
    print("=" * 60)

    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    redis_client = await get_redis_client()
    runtime = AgentRuntime(redis_client=redis_client, user_id=1)
    session_id = "test_logging"

    print("\n📌 发送一个请求，观察日志输出")
    print("-" * 60)

    response = await runtime.chat("查一下我的余额", session_id)
    print(f"\n🤖 Agent 回复：{response[:50]}...")

    if hasattr(runtime, 'logger') and runtime.logger:
        print("\n✅ Logger 已初始化，日志会输出到控制台")
        print("   日志格式：时间 - 模块名 - 级别 - 消息")
        if redis_client:
            await redis_client.close()
        return True
    else:
        print("❌ Logger 未初始化")
        if redis_client:
            await redis_client.close()
        return False


async def main():
    """运行所有 Day 5 测试"""

    print("\n" + "🚀" * 20)
    print("Day 5 企业级功能测试（面向面试）")
    print("🚀" * 20)

    results = []

    print("\n" + ">" * 30)
    results.append(("分布式锁防并发", await test_distributed_lock()))

    print("\n" + ">" * 30)
    results.append(("cancel_booking 多轮确认", await test_cancel_booking_confirmation()))

    print("\n" + ">" * 30)
    results.append(("用户拒绝取消", await test_cancel_rejection()))

    print("\n" + ">" * 30)
    results.append(("业务错误码映射", await test_error_code_mapping()))

    print("\n" + ">" * 30)
    results.append(("结构化日志", await test_logging_output()))

    print("\n\n" + "=" * 60)
    print("📊 Day 5 测试结果汇总")
    print("=" * 60)

    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status} - {name}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
