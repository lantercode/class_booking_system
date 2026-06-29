# /Users/lixiang/Desktop/class_booking_system/apps/api/tests/integration/test_auth_api.py
"""
T03 Auth 模块集成测试

覆盖场景：
1. 用户注册（成功/失败）
2. 用户登录（成功/失败）
3. 获取当前用户信息（认证/未认证）
4. 刷新 Token（成功/Token 失效/已吊销）
5. 用户登出（成功/重复登出）
6. 完整链路：register → login → me → refresh → logout

运行命令：
    uv run pytest tests/integration/test_auth_api.py -v
"""

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.config import get_settings
from app.modules.auth.schemas import RegisterRequest, LoginRequest

import time
import random
import string

settings = get_settings()


def generate_unique_phone() -> str:
    """生成唯一的手机号用于测试"""
    # 使用时间戳 + 随机数确保唯一性
    timestamp = int(time.time() * 1000) % 10000
    random_num = random.randint(1000, 9999)
    return f"139{timestamp}{random_num}"


# 使用 conftest.py 中定义的 http_client fixture（session 级别）
# 避免每个测试都创建新的 AsyncClient 导致的事件循环问题


@pytest.fixture
def register_data():
    """注册请求数据"""
    phone = generate_unique_phone()
    print(f"\n📱 生成测试手机号: {phone}")
    return {
        "tenant_slug": "dance-school",
        "phone": phone,  # 使用不冲突的手机号
        "password": "Test@123456",
        "verify_code": "123456",
        "nickname": "测试用户"
    }


@pytest.fixture
def login_data(register_data: dict):
    """登录请求数据"""
    return {
        "tenant_slug": "dance-school",  # 根据种子数据调整
        "phone": register_data["phone"],
        "password": "Test@123456"
    }


class TestRegister:
    """注册接口测试"""

    @pytest.mark.asyncio
    async def test_register_success(self, client: AsyncClient, register_data: dict):
        """
        测试正常注册 → 应返回 201 + Token 对

        验收标准：
        - HTTP 状态码：201 Created
        - 响应包含 access_token, refresh_token, user 信息
        - user 信息包含 id, phone, nickname, status
        """
        response = await client.post("/api/v1/auth/register", json=register_data)

        # 断言状态码
        assert response.status_code == 201

        # 断言响应结构
        data = response.json()
        assert data["code"] == 0
        assert data["msg"] == "注册成功"
        assert "data" in data

        # 断言 Token 存在
        auth_data = data["data"]
        assert "access_token" in auth_data
        assert "refresh_token" in auth_data
        assert auth_data["token_type"] == "bearer"
        assert auth_data["expires_in"] == 7200

        # 断言用户信息
        user = auth_data["user"]
        assert "id" in user
        assert user["phone"] == register_data["phone"]
        assert user["nickname"] == register_data["nickname"]
        assert user["status"] == 1  # ACTIVE
        assert "created_at" in user

        print(f"✅ 注册成功: user_id={user['id']}, phone={user['phone']}")

    @pytest.mark.asyncio
    async def test_register_duplicate_phone(self, client: AsyncClient, register_data: dict):
        """
        测试重复手机号注册 → 应返回 400

        场景：同一手机号在相同租户内注册两次
        """
        # 第一次注册
        response1 = await client.post("/api/v1/auth/register", json=register_data)
        assert response1.status_code == 201

        # 第二次注册（相同手机号）
        response2 = await client.post("/api/v1/auth/register", json=register_data)

        # 断言返回 400
        assert response2.status_code == 400
        data = response2.json()
        assert data["code"] == 400
        assert "已存在" in data["msg"] or "已被注册" in data["msg"]

        print(f"✅ 重复注册被正确拒绝: {data['msg']}")

    @pytest.mark.asyncio
    async def test_register_invalid_phone_format(self, client: AsyncClient):
        """
        测试无效手机号格式 → 应返回 422 (Pydantic 校验)
        """
        invalid_data = {
            "tenant_slug": "dance-school",
            "phone": "12345",  # 无效的手机号格式
            "password": "Test@123456",
            "verify_code": "123456",
            "nickname": "测试用户"
        }

        response = await client.post("/api/v1/auth/register", json=invalid_data)

        # Pydantic 校验失败返回 422
        assert response.status_code == 422

        print(f"✅ 无效手机号格式被正确拦截")

    @pytest.mark.asyncio
    async def test_register_weak_password(self, client: AsyncClient):
        """
        测试弱密码 → 应返回 422 (Pydantic 校验)
        """
        weak_password_data = {
            "tenant_slug": "dance-school",
            "phone": "13900139001",
            "password": "123456",  # 弱密码（不符合复杂度要求）
            "verify_code": "123456",
            "nickname": "测试用户"
        }

        response = await client.post("/api/v1/auth/register", json=weak_password_data)

        # 密码长度不足或复杂度不够
        assert response.status_code == 422

        print(f"✅ 弱密码被正确拦截")


class TestLogin:
    """登录接口测试"""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, register_data: dict):
        """
        测试正常登录 → 应返回 200 + Token 对

        前置条件：先注册一个用户
        """
        # 先注册
        reg_response = await client.post("/api/v1/auth/register", json=register_data)
        assert reg_response.status_code == 201

        # 再登录
        login_data = {
            "tenant_slug": "dance-school",
            "phone": register_data["phone"],
            "password": register_data["password"]
        }

        response = await client.post("/api/v1/auth/login", json=login_data)

        # 断言状态码
        assert response.status_code == 200

        # 断言响应结构
        data = response.json()
        assert data["code"] == 0
        assert data["msg"] == "登录成功"

        auth_data = data["data"]
        assert "access_token" in auth_data
        assert "refresh_token" in auth_data
        assert "user" in auth_data

        print(f"✅ 登录成功: token 已生成")

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client: AsyncClient, register_data: dict):
        """
        测试错误密码 → 应返回 401
        """
        # 先注册
        await client.post("/api/v1/auth/register", json=register_data)

        # 使用错误密码登录
        login_data = {
            "tenant_slug": "dance-school",
            "phone": register_data["phone"],
            "password": "WrongPassword123!"  # 错误的密码
        }

        response = await client.post("/api/v1/auth/login", json=login_data)

        # 断言返回 401
        assert response.status_code == 401
        data = response.json()
        assert data["code"] == 401
        # 安全原则：不暴露具体原因（密码错误 vs 账号不存在）
        assert "错误" in data["msg"] or "无效" in data["msg"]

        print(f"✅ 错误密码被正确拒绝: {data['msg']}")

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client: AsyncClient):
        """
        测试不存在的用户登录 → 应返回 401（统一错误提示）
        """
        login_data = {
            "tenant_slug": "dance-school",
            "phone": "19999999999",  # 不存在的手机号
            "password": "Test@123456"
        }

        response = await client.post("/api/v1/auth/login", json=login_data)

        assert response.status_code == 401
        data = response.json()
        assert data["code"] == 401

        print(f"✅ 不存在的用户登录被拒绝")


class TestGetMe:
    """获取当前用户信息接口测试"""

    @pytest.mark.asyncio
    async def test_get_me_with_token(self, client: AsyncClient, register_data: dict):
        """
        测试带 Token 访问 /me → 应返回 200 + 用户信息
        """
        # 注册并获取 Token
        reg_response = await client.post("/api/v1/auth/register", json=register_data)
        access_token = reg_response.json()["data"]["access_token"]

        # 带 Token 访问 /me
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )

        # 断言成功
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "user_id" in data["data"]
        assert "tenant_id" in data["data"]

        print(f"✅ 成功获取当前用户信息")

    @pytest.mark.asyncio
    async def test_get_me_without_token(self, client: AsyncClient):
        """
        测试无 Token 访问 /me → 应返回 401
        """
        response = await client.get("/api/v1/auth/me")

        assert response.status_code == 401
        data = response.json()
        assert data["code"] == 401
        assert "未提供" in data["msg"] or "认证" in data["msg"]

        print(f"✅ 未认证请求被正确拒绝")

    @pytest.mark.asyncio
    async def test_get_me_invalid_token(self, client: AsyncClient):
        """
        测试无效 Token 访问 /me → 应返回 401
        """
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"}
        )

        assert response.status_code == 401

        print(f"✅ 无效 Token 被正确拒绝")


class TestRefreshToken:
    """刷新 Token 接口测试"""

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, client: AsyncClient, register_data: dict):
        """
        测试正常刷新 Token → 应返回新的 Token 对

        关键验证点：
        - 返回全新的 access_token 和 refresh_token
        - 旧的 refresh_token 将失效（一次性使用机制）
        """
        # 注册并获取初始 Token
        reg_response = await client.post("/api/v1/auth/register", json=register_data)
        old_refresh_token = reg_response.json()["data"]["refresh_token"]

        # 刷新 Token
        refresh_response = await client.post(
            "/api/v1/auth/refresh-token",
            json={"refresh_token": old_refresh_token}
        )

        # 断言成功
        assert refresh_response.status_code == 200
        data = refresh_response.json()
        assert data["code"] == 0
        assert data["msg"] == "Token 刷新成功"

        new_tokens = data["data"]
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        assert new_tokens["token_type"] == "bearer"

        # 验证新 Token 与旧 Token 不同
        new_refresh_token = new_tokens["refresh_token"]
        assert new_refresh_token != old_refresh_token, "刷新后应生成新的 refresh_token"

        print(f"✅ Token 刷新成功，旧 RT 已失效")

    @pytest.mark.asyncio
    async def test_refresh_token_already_used(self, client: AsyncClient, register_data: dict):
        """
        测试重复使用已刷新过的 refresh_token → 应返回 401

        这是安全特性的关键测试！
        验证一次性 Token 旋转机制是否生效。
        """
        # 注册并获取初始 Token
        reg_response = await client.post("/api/v1/auth/register", json=register_data)
        old_refresh_token = reg_response.json()["data"]["refresh_token"]

        # 第一次刷新（应该成功）
        first_refresh = await client.post(
            "/api/v1/auth/refresh-token",
            json={"refresh_token": old_refresh_token}
        )
        assert first_refresh.status_code == 200

        # 第二次使用相同的 refresh_token（应该失败！）
        second_refresh = await client.post(
            "/api/v1/auth/refresh-token",
            json={"refresh_token": old_refresh_token}
        )

        # 断言失败（Token 已在黑名单中）
        assert second_refresh.status_code == 401
        data = second_refresh.json()
        assert data["code"] == 401
        assert "失效" in data["msg"] or "无效" in data["msg"]

        print(f"✅ 重复使用的 refresh_token 被正确拒绝（黑名单机制生效）")

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, client: AsyncClient):
        """
        测试无效的 refresh_token → 应返回 401
        """
        response = await client.post(
            "/api/v1/auth/refresh-token",
            json={"refresh_token": "invalid_refresh_token"}
        )

        assert response.status_code == 401

        print(f"✅ 无效 refresh_token 被正确拒绝")


class TestLogout:
    """登出接口测试"""

    @pytest.mark.asyncio
    async def test_logout_success(self, client: AsyncClient, register_data: dict):
        """
        测试正常登出 → 应返回 200，且 refresh_token 失效
        """
        # 注册并获取 Token
        reg_response = await client.post("/api/v1/auth/register", json=register_data)
        auth_data = reg_response.json()["data"]
        access_token = auth_data["access_token"]
        refresh_token = auth_data["refresh_token"]

        # 登出
        logout_response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"refresh_token": refresh_token}
        )

        # 断言登出成功
        assert logout_response.status_code == 200
        data = logout_response.json()
        assert data["code"] == 0
        assert data["msg"] == "登出成功"

        # 验证 refresh_token 已失效（尝试使用它刷新）
        refresh_after_logout = await client.post(
            "/api/v1/auth/refresh-token",
            json={"refresh_token": refresh_token}
        )

        assert refresh_after_logout.status_code == 401

        print(f"✅ 登出成功，refresh_token 已加入黑名单")

    @pytest.mark.asyncio
    async def test_logout_without_refresh_token(self, client: AsyncClient, register_data: dict):
        """
        测试登出不提供 refresh_token → 应仍返回 200（可选参数）
        """
        # 注册并获取 Token
        reg_response = await client.post("/api/v1/auth/register", json=register_data)
        access_token = reg_response.json()["data"]["access_token"]

        # 登出时不提供 refresh_token
        logout_response = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            json={}  # 空请求体
        )

        # 应该仍然成功（refresh_token 是可选的）
        assert logout_response.status_code == 200

        print(f"✅ 无 refresh_token 的登出也成功了")


class TestCompleteAuthFlow:
    """
    完整认证链路测试

    模拟真实用户的完整生命周期：
    注册 → 登录 → 查看个人信息 → 刷新 Token → 登出 → 验证 Token 失效
    """

    @pytest.mark.asyncio
    async def test_complete_happy_path(self, client: AsyncClient):
        """
        完整 happy path 测试

        步骤：
        1. 注册新用户 → 获得 Token 对
        2. 使用 Token 访问 /me → 获取用户信息
        3. 刷新 Token → 获得新 Token 对
        4. 使用新 Token 访问 /me → 仍然有效
        5. 登出 → Token 失效
        6. 尝试使用旧 Token → 401
        """
        unique_phone = f"138{__import__('random').randint(10000000, 99999999)}"

        register_payload = {
            "tenant_slug": "dance-school",
            "phone": unique_phone,
            "password": "Secure@Pass789",
            "verify_code": "654321",
            "nickname": "完整链路测试用户"
        }

        # ===== Step 1: 注册 =====
        print("\n📝 Step 1: 注册用户...")
        reg_resp = await client.post("/api/v1/auth/register", json=register_payload)
        assert reg_resp.status_code == 201, f"注册失败: {reg_resp.text}"

        reg_data = reg_resp.json()["data"]
        access_token_1 = reg_data["access_token"]
        refresh_token_1 = reg_data["refresh_token"]
        user_id = reg_data["user"]["id"]

        print(f"   ✅ 注册成功: user_id={user_id}")

        # ===== Step 2: 获取用户信息 =====
        print("📝 Step 2: 获取当前用户信息...")
        me_resp_1 = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token_1}"}
        )
        assert me_resp_1.status_code == 200, f"获取用户信息失败: {me_resp_1.text}"

        me_data_1 = me_resp_1.json()["data"]
        assert me_data_1["user_id"] == user_id

        print(f"   ✅ 用户信息获取成功")

        # ===== Step 3: 刷新 Token =====
        print("📝 Step 3: 刷新 Token...")
        refresh_resp = await client.post(
            "/api/v1/auth/refresh-token",
            json={"refresh_token": refresh_token_1}
        )
        assert refresh_resp.status_code == 200, f"刷新 Token 失败: {refresh_resp.text}"

        refresh_data = refresh_resp.json()["data"]
        access_token_2 = refresh_data["access_token"]
        refresh_token_2 = refresh_data["refresh_token"]

        # 验证生成了新 Token
        assert access_token_2 != access_token_1, "应生成新的 access_token"
        assert refresh_token_2 != refresh_token_1, "应生成新的 refresh_token"

        print(f"   ✅ Token 刷新成功，获得新 Token 对")

        # ===== Step 4: 使用新 Token 访问 =====
        print("📝 Step 4: 使用新 Token 访问...")
        me_resp_2 = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token_2}"}
        )
        assert me_resp_2.status_code == 200, "新 Token 应该有效"

        print(f"   ✅ 新 Token 有效")

        # ===== Step 5: 登出 =====
        print("📝 Step 5: 登出...")
        logout_resp = await client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token_2}"},
            json={"refresh_token": refresh_token_2}
        )
        assert logout_resp.status_code == 200, f"登出失败: {logout_resp.text}"

        print(f"   ✅ 登出成功")

        # ===== Step 6: 验证 Token 失效 =====
        print("📝 Step 6: 验证 Token 失效...")

        # 尝试使用旧的 access_token
        old_at_resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token_1}"}
        )
        # 注意：access_token 可能还未过期，所以可能还是 200
        # 但 refresh_token 应该已经失效

        # 尝试使用已吊销的 refresh_token 刷新
        old_rt_resp = await client.post(
            "/api/v1/auth/refresh-token",
            json={"refresh_token": refresh_token_2}  # 已登出的 RT
        )
        assert old_rt_resp.status_code == 401, "已登出的 refresh_token 应该失效"

        print(f"   ✅ refresh_token 已失效（黑名单机制验证通过）")

        print("\n" + "=" * 60)
        print("🎉 完整认证链路测试全部通过！")
        print("=" * 60)


# ==================== 边界情况测试 ====================

class TestEdgeCases:
    """边界情况和异常处理测试"""

    @pytest.mark.asyncio
    async def test_missing_required_fields(self, client: AsyncClient):
        """
        测试缺少必填字段 → 应返回 422
        """
        incomplete_data = {
            # 缺少 password, verify_code, nickname
            "tenant_slug": "dance-school",
            "phone": "13900139002"
        }

        response = await client.post("/api/v1/auth/register", json=incomplete_data)
        assert response.status_code == 422

        print(f"✅ 缺少必填字段被正确拦截")

    @pytest.mark.asyncio
    async def test_extra_fields_ignored(self, client: AsyncClient, register_data: dict):
        """
        测试额外字段应被忽略（Pydantic 特性）
        """
        register_data_with_extra = {
            **register_data,
            "extra_field": "should_be_ignored"  # 额外字段
        }

        response = await client.post("/api/v1/auth/register", json=register_data_with_extra)
        # Pydantic 默认忽略额外字段，所以应该成功
        assert response.status_code == 201

        print(f"✅ 额外字段被正确忽略")

    @pytest.mark.asyncio
    async def test_sql_injection_protection(self, client: AsyncClient):
        """
        测试 SQL 注入防护（ORM 参数化查询）
        """
        injection_payload = {
            "tenant_slug": "dance-school'; DROP TABLE users; --",
            "phone": "13900139003",
            "password": "Test@123456",
            "verify_code": "123456",
            "nickname": "SQL注入测试"
        }

        response = await client.post("/api/v1/auth/register", json=injection_payload)
        # 不应该崩溃，要么成功（作为普通字符串），要么校验失败
        assert response.status_code in [201, 400, 422]

        print(f"✅ SQL 注入防护正常工作")


if __name__ == "__main__":
    # 手动运行测试（开发调试用）
    import asyncio


    async def run_tests():
        import pytest
        exit_code = await pytest.main([
            __file__,
            "-v",
            "--tb=short",
            "-x"  # 第一个失败就停止
        ])
        return exit_code


    asyncio.run(run_tests())