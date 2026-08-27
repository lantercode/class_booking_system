"""
MCP Server 数据连通性测试脚本
验证所有 Tool 能否正确调用真实 Service 并返回数据

用法：
    cd apps/api
    PYTHONPATH=src .venv/bin/python tests/test_mcp_server.py
"""

import asyncio

from app.ai.mcp_server import (
    create_booking,
    get_my_balance,
    get_my_bookings,
    query_courses,
    query_schedules,
)

# 替换为你数据库中实际存在的 student_id
TEST_USER_ID = 1


async def test_query_courses():
    """测试：搜索课程"""
    print("=" * 60)
    print("1. 测试 query_courses")
    print("=" * 60)

    print("\n>>> 全量查询")
    print(await query_courses(keyword=""))

    print("\n>>> 关键词查询")
    print(await query_courses(keyword="yoga"))


async def test_query_schedules():
    """测试：查询排期"""
    print("\n" + "=" * 60)
    print("2. 测试 query_schedules")
    print("=" * 60)

    print("\n>>> 未来 7 天排期")
    print(await query_schedules(days=7))

    print("\n>>> 未来 30 天排期")
    print(await query_schedules(days=30))


async def test_get_my_balance():
    """测试：查询课时余额"""
    print("\n" + "=" * 60)
    print("3. 测试 get_my_balance")
    print("=" * 60)

    print(f"\n>>> 用户 {TEST_USER_ID} 的余额")
    print(await get_my_balance(user_id=TEST_USER_ID))


async def test_get_my_bookings():
    """测试：查询预约记录"""
    print("\n" + "=" * 60)
    print("4. 测试 get_my_bookings")
    print("=" * 60)

    print(f"\n>>> 用户 {TEST_USER_ID} 的全部预约")
    print(await get_my_bookings(user_id=TEST_USER_ID))

    print(f"\n>>> 用户 {TEST_USER_ID} 的已预约")
    print(await get_my_bookings(user_id=TEST_USER_ID, status="booked"))


async def test_create_and_cancel():
    """测试：创建 + 取消预约（谨慎使用）"""
    print("\n" + "=" * 60)
    print("5. 测试 create_booking / cancel_booking")
    print("=" * 60)

    # 先查排期，获取一个可用的 schedule_id
    print("\n>>> 先查可用排期...")
    schedules_text = await query_schedules(days=7)
    print(schedules_text)

    # 手动指定 schedule_id 测试
    print("\n>>> 创建预约（schedule_id=1，如果不存在会报错）")
    print(await create_booking(schedule_id=1, user_id=TEST_USER_ID))


async def main():
    print(f"""
╔══════════════════════════════════════════════════════╗
║         MCP Server 数据连通性测试                      ║
║         测试用户 ID: {TEST_USER_ID:<30} ║
╚══════════════════════════════════════════════════════╝
""")

    await test_query_courses()
    await test_query_schedules()
    await test_get_my_balance()
    await test_get_my_bookings()

    # 操作类测试默认跳过，取消注释手动运行
    # await test_create_and_cancel()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
