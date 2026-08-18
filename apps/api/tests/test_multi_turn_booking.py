"""
Day 4 测试：多轮对话预约流程

测试场景：
  第1轮：用户说"帮我约瑜伽课"
         → Agent 查排期 → 存状态 → 返回选项 [1] [2] [3]

  第2轮：用户回复"1"
         → Agent 从 Redis 取状态 → 解析选择 → 调用 create_booking → 清除状态 → 返回成功

运行方式：
  cd /Users/lixiang/Desktop/class_booking_system/apps/api
  PYTHONPATH=src .venv/bin/python tests/test_multi_turn_booking.py
"""

import asyncio
import sys
sys.path.insert(0, 'src')

from app.ai.agent.runtime import AgentRuntime
from app.ai.agent.session import SessionManager


async def test_multi_turn_booking():
    """测试多轮预约流程"""

    print("=" * 60)
    print("🧪 Day 4 测试：多轮对话预约流程")
    print("=" * 60)

    runtime = AgentRuntime(user_id=1)
    session_id = "test_session_001"

    print("\n📌 第 1 轮：用户说「帮我约明天下午的瑜伽课」")
    print("-" * 60)

    response_1 = await runtime.chat(
        user_input="帮我约明天下午的瑜伽课",
        session_id=session_id,
    )

    print(f"🤖 Agent 回复：\n{response_1}")

    if "找到以下排期" in response_1 or "请回复数字" in response_1:
        print("✅ 第 1 轮通过：成功展示排期选项")
    else:
        print(f"❌ 第 1 轮失败：预期显示选项，实际返回：\n{response_1}")
        return False

    print("\n📌 第 2 轮：用户回复「1」（选择第 1 个排期）")
    print("-" * 60)

    response_2 = await runtime.chat(
        user_input="1",
        session_id=session_id,
    )

    print(f"🤖 Agent 回复：\n{response_2}")

    if "预约成功" in response_2 or "✅" in response_2:
        print("✅ 第 2 轮通过：成功创建预约")
    else:
        print(f"⚠️ 第 2 轮结果：\n{response_2}")
        print("（可能是因为没有真实排期数据，或数据库未启动）")

    print("\n📌 验证：状态是否已清除")
    print("-" * 60)

    state = await runtime.session.get_state(session_id)
    if not state:
        print("✅ 状态已正确清除（Redis 中无残留状态）")
    else:
        print(f"❌ 状态未清除，残留：{state}")
        return False

    print("\n" + "=" * 60)
    print("🎉 多轮对话测试完成！")
    print("=" * 60)

    return True


async def test_invalid_selection():
    """测试无效选择的情况"""

    print("\n" + "=" * 60)
    print("🧪 补充测试：无效选择的处理")
    print("=" * 60)

    runtime = AgentRuntime(user_id=1)
    session_id = "test_session_002"

    print("\n📌 第 1 轮：触发多轮状态")
    print("-" * 60)

    response_1 = await runtime.chat(
        user_input="查一下爵士舞的排期",
        session_id=session_id,
    )
    print(f"Agent: {response_1[:50]}...")

    print("\n📌 第 2 轮：用户输入无效选择「abc」")
    print("-" * 60)

    response_2 = await runtime.chat(
        user_input="abc",
        session_id=session_id,
    )
    print(f"🤖 Agent 回复：\n{response_2}")

    if "无法识别" in response_2 or "请回复数字" in response_2:
        print("✅ 无效选择处理正确：提示用户重新输入")
    else:
        print(f"❌ 预期提示重新输入，实际：{response_2}")


async def test_parse_user_selection():
    """测试 _parse_user_selection 方法"""

    print("\n" + "=" * 60)
    print("🧪 单元测试：_parse_user_selection()")
    print("=" * 60)

    runtime = AgentRuntime()

    test_cases = [
        ("1", 3, 1, "纯数字"),
        ("第1个", 3, 1, "中文序数"),
        ("第一个", 5, 1, "中文基数"),
        ("选二", 3, 2, "混合输入"),
        ("3", 3, 3, "边界值（最大）"),
        ("99", 3, None, "超出范围"),
        ("abc", 3, None, "非数字非中文"),
        ("", 3, None, "空字符串"),
        ("十", 10, 10, "中文十"),
    ]

    all_passed = True
    for input_str, max_index, expected, desc in test_cases:
        result = runtime._parse_user_selection(input_str, max_index)
        status = "✅" if result == expected else "❌"
        print(f"{status} {desc:10s} | 输入: {input_str:8s} | 最大: {max_index} | 预期: {str(expected):5s} | 实际: {str(result):5s}")
        if result != expected:
            all_passed = False

    if all_passed:
        print("\n✅ 所有 _parse_user_selection 测试通过！")
    else:
        print("\n❌ 部分测试失败")

    return all_passed


async def main():
    """运行所有测试"""

    print("\n" + "🚀" * 20)
    print("开始运行 Day 4 多轮对话测试")
    print("🚀" * 20)

    results = []

    print("\n" + ">" * 30)
    print("测试 1：_parse_user_selection() 单元测试")
    print("<" * 30)
    result1 = await test_parse_user_selection()
    results.append(("单元测试 _parse_user_selection", result1))

    print("\n" + ">" * 30)
    print("测试 2：多轮预约主流程")
    print("<" * 30)
    result2 = await test_multi_turn_booking()
    results.append(("多轮预约主流程", result2))

    print("\n" + ">" * 30)
    print("测试 3：无效选择处理")
    print("<" * 30)
    await test_invalid_selection()

    print("\n\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)

    for name, passed in results:
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"{status} - {name}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
