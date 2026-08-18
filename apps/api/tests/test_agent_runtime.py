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

    agent = AgentRuntime(user_id=TEST_USER_ID)

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


async def main():
    print("""
╔══════════════════════════════════════════════════════╗
║         Agent Runtime 全链路测试                      ║
╚══════════════════════════════════════════════════════╝
""")

    await test_intent_recognizer()
    await test_agent_chat()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())