"""
Agent Runtime 测试脚本
验证意图识别 → Tool 调用 → 回复格式化 全链路

用法：
    cd apps/api
    PYTHONPATH=src .venv/bin/python tests/test_agent_runtime.py
"""

import asyncio

from app.ai.agent import AgentRuntime, IntentRecognizer

# 替换为你数据库中实际存在的 student_id
TEST_USER_ID = 1


async def test_intent_recognizer():
    """测试：意图识别"""
    print("=" * 60)
    print("1. 意图识别测试")
    print("=" * 60)

    recognizer = IntentRecognizer()

    cases = [
        ("帮我预约明天下午的瑜伽课", "create_booking"),
        ("查一下街舞课程", "query_courses"),
        ("明天有什么课", "query_schedules"),
        ("我的预约记录", "get_my_bookings"),
        ("还剩多少课时", "get_my_balance"),
        ("取消预约", "cancel_booking"),
        ("今天天气怎么样", "unknown"),
    ]

    for text, expected in cases:
        result = recognizer.recognize(text)
        status = "✅" if result["intent"] == expected else "❌"
        print(f"  {status} 「{text}」")
        print(f"     意图={result['intent']} (期望={expected}), 参数={result['params']}")


async def test_agent_chat():
    """测试：Agent 完整对话流程"""
    print("\n" + "=" * 60)
    print("2. Agent 对话测试")
    print("=" * 60)

    agent = AgentRuntime(user_id=TEST_USER_ID, tenant_id=1)

    queries = [
        "查一下瑜伽课",
        "明天有什么课",
        "我的余额",
        "我的预约",
    ]

    for q in queries:
        print(f"\n>>> 用户: {q}")
        response = await agent.chat(q)
        print(f"    助手: {response[:200]}{'...' if len(response) > 200 else ''}")


async def test_business_error_handling():
    """F5.3：业务异常映射友好提示，不回显原始异常"""
    print("\n" + "=" * 60)
    print("3. 业务异常友好映射测试（F5.3）")
    print("=" * 60)

    agent = AgentRuntime(user_id=TEST_USER_ID, tenant_id=1)

    cases = [
        (Exception("该排期已约满"), "约满", "SCHEDULE_FULL"),
        (Exception("您已预约该排期，请勿重复预约"), "已预约", "ALREADY_BOOKED"),
        (Exception("会员卡扣次失败，预约已撤销"), "余额不足", "BALANCE"),
        (Exception("未找到该预约记录"), "未找到", "NOT_FOUND"),
        (Exception("已超过取消截止时间"), "取消", "CANCEL_DEADLINE"),
        (Exception("该课程已开始，无法预约"), "已开始", "EXPIRED"),
        (Exception("只能预约未来两周内的课程"), "两周", "TOO_FAR"),
        (Exception("预约已取消"), "取消", "CANCELLED"),
        (Exception("当前预约状态无法签到"), "状态", "STATUS"),
        (Exception("未知的内部错误 SQL: SELECT * FROM"), "操作失败", "FALLBACK"),
    ]

    all_pass = True
    for exc, keyword, label in cases:
        result = agent._handle_business_error(exc)
        original = str(exc)
        leaked = original in result
        matched = keyword in result
        status = "✅" if (matched and not leaked) else "❌"
        if not (matched and not leaked):
            all_pass = False
        print(f"  {status} [{label}] 匹配={'是' if matched else '否'} 泄露={'是' if leaked else '否'}")
        print(f"      输入: {original}")
        print(f"      输出: {result[:80]}")

    assert all_pass, "存在未正确映射或泄露原始异常的用例"
    print("\n✅ 所有业务异常均友好映射且未泄露原始信息")


async def test_parse_schedules_unified_format():
    """F5.1：_parse_schedules 能正确解析 query_schedules 的统一输出格式"""
    print("\n" + "=" * 60)
    print("4. 排期统一格式解析测试（F5.1）")
    print("=" * 60)

    agent = AgentRuntime(user_id=TEST_USER_ID, tenant_id=1)

    # 该字符串必须与 mcp_server.query_schedules 实际输出格式逐字符一致
    sample = (
        "2026-09-27 至 2026-10-04 共 2 个排期：\n"
        "- ID:5 | 2026-09-27 | 14:00-15:00 | 王老师 | 剩余:3 | 瑜伽课\n"
        "- ID:8 | 2026-09-28 | 10:00-11:30 | 李老师 | 剩余:0 | 街舞课"
    )

    schedules = agent._parse_schedules(sample)

    assert len(schedules) == 2, f"期望解析 2 条，实际 {len(schedules)}"

    s1 = schedules[0]
    assert s1["id"] == 5
    assert s1["date"] == "2026-09-27"
    assert s1["time"] == "14:00-15:00"
    assert s1["teacher"] == "王老师"
    assert s1["remaining"] == 3
    assert s1["course_name"] == "瑜伽课"

    s2 = schedules[1]
    assert s2["id"] == 8
    assert s2["remaining"] == 0  # 已满时 remaining=0
    assert s2["course_name"] == "街舞课"

    # 无排期时返回空列表
    empty = agent._parse_schedules("2026-09-27 至 2026-10-04 暂无排期")
    assert empty == []

    # 展示格式包含课程名与剩余名额
    options = agent._format_schedule_options(schedules)
    assert "瑜伽课" in options
    assert "街舞课" in options
    assert "剩余3个" in options
    assert "[1]" in options and "[2]" in options

    print("  ✅ 统一格式解析正确（id/date/time/teacher/remaining/course_name）")
    print("  ✅ 已满排期 remaining=0 解析正确")
    print("  ✅ 无排期返回空列表")
    print("  ✅ 选项展示包含课程名与剩余名额")


async def test_booking_flow_end_to_end(monkeypatch=None):
    """F5.1：端到端模拟多轮预约流程（mock Tool，不依赖 DB）"""
    print("\n" + "=" * 60)
    print("5. 多轮预约流程端到端模拟（F5.1）")
    print("=" * 60)

    import app.ai.agent.runtime as runtime_mod

    # 内存版 FakeRedis，支撑 SessionManager 的 state / lock 存取
    class FakeRedis:
        def __init__(self):
            self.store = {}

        async def get(self, key):
            return self.store.get(key)

        async def set(self, key, value, nx=False, ex=None):
            if nx and key in self.store:
                return False
            self.store[key] = value
            return True

        async def delete(self, key):
            self.store.pop(key, None)

        async def eval(self, script, numkeys, *keys_and_args):
            key = keys_and_args[0]
            expected = keys_and_args[1] if len(keys_and_args) > 1 else None
            if self.store.get(key) == expected:
                self.store.pop(key, None)
                return 1
            return 0

    # mock query_schedules：返回统一格式排期
    async def fake_query_schedules(**kwargs):
        return (
            "2026-09-27 至 2026-10-04 共 1 个排期：\n"
            "- ID:42 | 2026-09-27 | 14:00-15:00 | 王老师 | 剩余:5 | 瑜伽课"
        )

    # mock create_booking：记录调用并返回成功
    booked = {}

    async def fake_create_booking(schedule_id, user_id, tenant_id):
        booked["schedule_id"] = schedule_id
        booked["user_id"] = user_id
        booked["tenant_id"] = tenant_id
        return "预约成功！\n课程：瑜伽课\n时间：09/27 14:00\n预约ID：999"

    runtime_mod.query_schedules = fake_query_schedules
    runtime_mod.create_booking = fake_create_booking

    try:
        agent = AgentRuntime(
            redis_client=FakeRedis(), user_id=TEST_USER_ID, tenant_id=1
        )

        # 第 1 轮：用户说"预约明天的瑜伽课"，无 schedule_id → 查排期 → 返回选项
        r1 = await agent.chat("预约明天的瑜伽课")
        assert "找到以下排期" in r1, f"第1轮未返回排期选项: {r1}"
        assert "瑜伽课" in r1
        assert "[1]" in r1
        print("  ✅ 第1轮：返回排期选项列表")

        # 第 2 轮：用户回复"1" → 解析选择 → 调 create_booking → 成功
        r2 = await agent.chat("1")
        assert "预约成功" in r2, f"第2轮未预约成功: {r2}"
        assert booked["schedule_id"] == 42
        assert booked["user_id"] == TEST_USER_ID
        assert "瑜伽课" in r2
        print("  ✅ 第2轮：用户选 1 → 预约成功，schedule_id=42")

        # 状态已清除（再次发消息不会被当作选择）
        r3 = await agent.chat("查排期")
        assert "找到以下排期" not in r3 or "排期查询结果" in r3
        print("  ✅ 预约后状态已清除，对话可继续")

    finally:
        # 恢复原始引用
        from app.ai.mcp_server import create_booking as _cb, query_schedules as _qs

        runtime_mod.query_schedules = _qs
        runtime_mod.create_booking = _cb


async def main():
    print("""
╔══════════════════════════════════════════════════════╗
║         Agent Runtime 全链路测试                      ║
╚══════════════════════════════════════════════════════╝
""")

    await test_intent_recognizer()
    await test_agent_chat()
    await test_business_error_handling()
    await test_parse_schedules_unified_format()
    await test_booking_flow_end_to_end()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
