#!/usr/bin/env python3
"""
诊断会员卡数据异常脚本

用于检查：
1. used_credits > total_credits 的异常卡
2. used_credits < 0 的异常卡
3. 期卡（应该 unlimited）但 total_credits 有值的卡
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.modules.membership.models import MembershipCard


async def diagnose():
    settings = get_settings()
    
    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )
    
    async with engine.begin() as conn:
        # 检查 1: used_credits > total_credits
        print("=" * 80)
        print("检查 1: used_credits > total_credits 的异常卡")
        print("=" * 80)
        
        result = await conn.execute(text("""
            SELECT id, student_id, product_id, card_type, total_credits, used_credits, 
                   (total_credits - used_credits) as remaining, status
            FROM membership_cards
            WHERE total_credits IS NOT NULL 
              AND used_credits > total_credits
            ORDER BY id
        """))
        
        rows = result.fetchall()
        if rows:
            print(f"\n发现 {len(rows)} 张异常卡：\n")
            for row in rows:
                print(f"  卡ID: {row[0]}")
                print(f"  学员ID: {row[1]}")
                print(f"  产品ID: {row[2]}")
                print(f"  卡类型: {row[3]}")
                print(f"  总次数: {row[4]}")
                print(f"  已使用: {row[5]}")
                print(f"  剩余: {row[6]}")
                print(f"  状态: {row[7]}")
                print("-" * 40)
        else:
            print("✅ 未发现异常")
        
        # 检查 2: used_credits < 0
        print("\n" + "=" * 80)
        print("检查 2: used_credits < 0 的异常卡")
        print("=" * 80)
        
        result = await conn.execute(text("""
            SELECT id, student_id, product_id, card_type, total_credits, used_credits, status
            FROM membership_cards
            WHERE used_credits < 0
            ORDER BY id
        """))
        
        rows = result.fetchall()
        if rows:
            print(f"\n发现 {len(rows)} 张异常卡：\n")
            for row in rows:
                print(f"  卡ID: {row[0]}")
                print(f"  学员ID: {row[1]}")
                print(f"  产品ID: {row[2]}")
                print(f"  卡类型: {row[3]}")
                print(f"  总次数: {row[4]}")
                print(f"  已使用: {row[5]}")
                print(f"  状态: {row[6]}")
                print("-" * 40)
        else:
            print("✅ 未发现异常")
        
        # 检查 3: 期卡但有 total_credits 限制
        print("\n" + "=" * 80)
        print("检查 3: 期卡（time_card）但有 total_credits 限制的卡")
        print("=" * 80)
        
        result = await conn.execute(text("""
            SELECT id, student_id, product_id, card_type, total_credits, used_credits, 
                   valid_from, expire_at, status
            FROM membership_cards
            WHERE card_type = 'time' 
              AND total_credits IS NOT NULL
            ORDER BY id
        """))
        
        rows = result.fetchall()
        if rows:
            print(f"\n发现 {len(rows)} 张期卡有次数限制（可能是配置错误）：\n")
            for row in rows:
                print(f"  卡ID: {row[0]}")
                print(f"  学员ID: {row[1]}")
                print(f"  产品ID: {row[2]}")
                print(f"  卡类型: {row[3]}")
                print(f"  总次数: {row[4]} ⚠️ 期卡应该为 NULL")
                print(f"  已使用: {row[5]}")
                print(f"  有效期: {row[6]} ~ {row[7]}")
                print(f"  状态: {row[8]}")
                print("-" * 40)
        else:
            print("✅ 未发现异常")
        
        # 检查 4: 特定卡ID的详细信息（从错误信息中获取）
        print("\n" + "=" * 80)
        print("检查 4: 错误信息中的卡（card_id=21）")
        print("=" * 80)
        
        result = await conn.execute(text("""
            SELECT id, student_id, product_id, card_type, total_credits, used_credits, 
                   (total_credits - used_credits) as remaining, valid_from, expire_at, status
            FROM membership_cards
            WHERE id = 21
        """))
        
        row = result.fetchone()
        if row:
            print(f"\n卡ID: {row[0]}")
            print(f"学员ID: {row[1]}")
            print(f"产品ID: {row[2]}")
            print(f"卡类型: {row[3]}")
            print(f"总次数: {row[4]}")
            print(f"已使用: {row[5]}")
            print(f"剩余: {row[6]}")
            print(f"有效期: {row[7]} ~ {row[8]}")
            print(f"状态: {row[9]}")
            
            if row[4] is not None and row[5] >= row[4]:
                print("\n⚠️ 警告：该卡次数已用完或已超额使用！")
            if row[3] == 'time' and row[4] is not None:
                print("\n⚠️ 警告：期卡不应该有次数限制，建议将 total_credits 设为 NULL")
        else:
            print("❌ 卡ID=21 不存在")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(diagnose())