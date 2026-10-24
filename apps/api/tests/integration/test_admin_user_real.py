"""
F2.1 admin 用户管理真实化 - 集成测试

验证目标（对应 Feature 2.1 Acceptance Criteria）：
- AC-1/2：创建用户真实落库；重复手机号 400
- AC-3：更新真实生效（username→nickname、is_active→status 映射）
- AC-4/5：删除真实生效（软删）；不能删除自己 400
- AC-6/15：列表真实分页；响应含 username/is_active 兼容别名
- AC-7/8：assign-roles 真实生效且清权限缓存
- AC-9/10/11：batch-delete 真实、原子（任一失败全回滚）、拒绝删自己
- AC-12：public/stats 真实聚合
- AC-17：PUT 传 role_ids 后权限缓存被清除

前置条件：
- 种子数据已由 conftest.seed_test_database 初始化
  （super_admin=13800000001 / teacher=13800138001 / student=13900139001，密码均为 Test@123456）
- Redis 可用（权限缓存断言）

运行方式：
    cd apps/api && PYTHONPATH=src .venv/bin/python -m pytest tests/integration/test_admin_user_real.py -v
"""

import time
from uuid import uuid4

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis

from app.core.config import get_settings

TENANT_HEADERS = {"x-tenant-slug": "dance-school"}
SUPER_ADMIN = {"phone": "13800000001", "password": "Test@123456"}  # super_admin 角色

BASE = "/api/v1/admin"


def _unique_phone() -> str:
    """生成符合 ^1[3-9]\\d{9}$ 的唯一手机号"""
    return f"139{(time.time_ns() // 1000 + uuid4().int) % 100000000:08d}"


async def _login(client: AsyncClient, account: dict) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"tenant_slug": "dance-school", **account},
    )
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    body = resp.json()
    assert body["code"] == 0, f"登录业务失败: {body}"
    return body["data"]["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", **TENANT_HEADERS}


@pytest.fixture
async def admin_token(client: AsyncClient) -> str:
    return await _login(client, SUPER_ADMIN)


async def _create_user(client: AsyncClient, token: str, **overrides) -> dict:
    """创建测试用户并返回响应 data"""
    payload = {
        "username": f"测试用户{uuid4().hex[:6]}",
        "phone": _unique_phone(),
        "password": "Test@123456",
        "is_active": True,
        "role_ids": [],
        **overrides,
    }
    resp = await client.post(f"{BASE}/users", json=payload, headers=_headers(token))
    assert resp.status_code == 201, f"创建用户失败: {resp.text}"
    body = resp.json()
    assert body["code"] == 0, f"创建用户业务失败: {body}"
    return body["data"]


async def _get_role_id(client: AsyncClient, token: str, code: str) -> int:
    resp = await client.get("/api/v1/roles", headers=_headers(token))
    assert resp.status_code == 200, f"获取角色列表失败: {resp.text}"
    items = resp.json()["data"]["items"]
    role = next(r for r in items if r["code"] == code)
    return role["id"]


@pytest.mark.asyncio
class TestAdminUserReal:
    """F2.1 admin 用户管理真实化"""

    async def test_create_user_real_and_alias(self, client: AsyncClient, admin_token: str):
        """AC-1/15：创建真实落库；id 非 Mock 9999；含 username/is_active 兼容别名"""
        phone = _unique_phone()
        data = await _create_user(client, admin_token, phone=phone, username="真实学员甲")

        assert data["id"] != 9999, "仍是 Mock id=9999"
        assert data["phone"] == phone
        assert data["username"] == "真实学员甲", "username 别名应映射 nickname"
        assert data["is_active"] is True
        assert data["tenant_id"], "tenant_id 应由租户上下文注入"

        # DB 可查：通过详情接口核对
        resp = await client.get(f"{BASE}/users/{data['id']}", headers=_headers(admin_token))
        assert resp.status_code == 200
        detail = resp.json()["data"]
        assert detail["phone"] == phone
        assert detail["nickname"] == "真实学员甲"

    async def test_create_user_duplicate_phone(self, client: AsyncClient, admin_token: str):
        """AC-2：重复手机号 400"""
        phone = _unique_phone()
        await _create_user(client, admin_token, phone=phone)

        payload = {
            "username": "重复手机号用户",
            "phone": phone,
            "password": "Test@123456",
            "is_active": True,
            "role_ids": [],
        }
        resp = await client.post(f"{BASE}/users", json=payload, headers=_headers(admin_token))
        assert resp.status_code == 400, f"重复手机号应 400，实际 {resp.status_code}: {resp.text}"
        assert "手机号" in resp.json()["msg"]

    async def test_update_user_real(self, client: AsyncClient, admin_token: str):
        """AC-3：更新真实生效；is_active=false → status=0；username → nickname"""
        created = await _create_user(client, admin_token)

        resp = await client.put(
            f"{BASE}/users/{created['id']}",
            json={"username": "改名后的用户", "is_active": False},
            headers=_headers(admin_token),
        )
        assert resp.status_code == 200, f"更新失败: {resp.text}"
        updated = resp.json()["data"]
        assert updated["nickname"] == "改名后的用户"
        assert updated["username"] == "改名后的用户", "username 别名应跟随 nickname"
        assert updated["status"] == 0
        assert updated["is_active"] is False

        # 详情复核落库结果
        detail = (
            await client.get(f"{BASE}/users/{created['id']}", headers=_headers(admin_token))
        ).json()["data"]
        assert detail["nickname"] == "改名后的用户"
        assert detail["status"] == 0

    async def test_delete_user_real(self, client: AsyncClient, admin_token: str):
        """AC-4：软删除真实生效，删除后详情 404"""
        created = await _create_user(client, admin_token)

        resp = await client.delete(f"{BASE}/users/{created['id']}", headers=_headers(admin_token))
        assert resp.status_code == 200, f"删除失败: {resp.text}"

        resp = await client.get(f"{BASE}/users/{created['id']}", headers=_headers(admin_token))
        assert resp.status_code == 404, f"删除后详情应 404，实际 {resp.status_code}"

    async def test_delete_self_forbidden(self, client: AsyncClient, admin_token: str):
        """AC-5：不能删除自己（400）"""
        resp = await client.get(
            f"{BASE}/users", params={"keyword": SUPER_ADMIN["phone"]}, headers=_headers(admin_token)
        )
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        self_id = next(u["id"] for u in items if u["phone"] == SUPER_ADMIN["phone"])

        resp = await client.delete(f"{BASE}/users/{self_id}", headers=_headers(admin_token))
        assert resp.status_code == 400, f"删除自己应 400，实际 {resp.status_code}"
        assert "不能删除自己" in resp.json()["msg"]

    async def test_list_users_real(self, client: AsyncClient, admin_token: str):
        """AC-6：列表返回真实数据（含种子用户），非 Mock user_N"""
        resp = await client.get(
            f"{BASE}/users",
            params={"keyword": "13800000001"},
            headers=_headers(admin_token),
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 1
        phones = [u["phone"] for u in data["items"]]
        assert "13800000001" in phones, "列表应包含种子管理员"
        assert all(not u["username"].startswith("user_") for u in data["items"]), (
            "列表不应含 Mock 的 user_N 数据"
        )

    async def test_assign_roles_real_and_cache_cleared(self, client: AsyncClient, admin_token: str):
        """AC-7/8：assign-roles 真实生效；目标用户权限缓存被清除

        注意：assign-roles 路由要求 admin/manager 角色（super_admin 不在其列），
        因此先创建一个 admin 角色用户作为操作人。
        """
        admin_role_id = await _get_role_id(client, admin_token, "admin")
        student_role_id = await _get_role_id(client, admin_token, "student")

        # 操作人：admin 角色用户
        operator = await _create_user(
            client, admin_token, username="角色管理员", role_ids=[admin_role_id]
        )
        operator_token = await _login(
            client, {"phone": operator["phone"], "password": "Test@123456"}
        )

        # 目标用户：无角色
        target = await _create_user(client, admin_token, username="被分配者")

        # 预置目标用户权限缓存，验证分配后被清除
        redis = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
        cache_key = f"perms:{target['tenant_id']}:{target['id']}"
        try:
            await redis.sadd(cache_key, "user:read")
            await redis.expire(cache_key, 300)
            assert await redis.exists(cache_key)

            resp = await client.post(
                f"{BASE}/users/{target['id']}/assign-roles",
                params={"role_ids": [student_role_id]},
                headers=_headers(operator_token),
            )
            assert resp.status_code == 200, f"分配角色失败: {resp.text}"
            assert resp.json()["data"]["role_ids"] == [student_role_id]

            # 缓存已清除
            assert not await redis.exists(cache_key), "分配角色后权限缓存未清除"
        finally:
            await redis.delete(cache_key)
            await redis.close()

        # 角色真实生效
        detail = (
            await client.get(f"{BASE}/users/{target['id']}", headers=_headers(admin_token))
        ).json()["data"]
        assert "student" in detail["roles"]

    async def test_update_with_role_ids_clears_cache(self, client: AsyncClient, admin_token: str):
        """AC-17：PUT 传 role_ids 后目标用户权限缓存被清除"""
        student_role_id = await _get_role_id(client, admin_token, "student")
        target = await _create_user(client, admin_token)

        redis = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)
        cache_key = f"perms:{target['tenant_id']}:{target['id']}"
        try:
            await redis.sadd(cache_key, "user:read")
            await redis.expire(cache_key, 300)

            resp = await client.put(
                f"{BASE}/users/{target['id']}",
                json={"role_ids": [student_role_id]},
                headers=_headers(admin_token),
            )
            assert resp.status_code == 200, f"更新角色失败: {resp.text}"
            assert not await redis.exists(cache_key), "更新角色后权限缓存未清除"
        finally:
            await redis.delete(cache_key)
            await redis.close()

    async def test_batch_delete_real(self, client: AsyncClient, admin_token: str):
        """AC-9：批量删除真实生效"""
        u1 = await _create_user(client, admin_token)
        u2 = await _create_user(client, admin_token)

        resp = await client.post(
            f"{BASE}/users/batch-delete",
            params={"user_ids": [u1["id"], u2["id"]]},
            headers=_headers(admin_token),
        )
        assert resp.status_code == 200, f"批量删除失败: {resp.text}"
        assert resp.json()["data"]["deleted_count"] == 2

        for uid in (u1["id"], u2["id"]):
            resp = await client.get(f"{BASE}/users/{uid}", headers=_headers(admin_token))
            assert resp.status_code == 404, f"用户 {uid} 删除后详情应 404，实际 {resp.status_code}"

    async def test_batch_delete_atomic(self, client: AsyncClient, admin_token: str):
        """AC-10：任一失败整体回滚（原子语义）"""
        real_user = await _create_user(client, admin_token)

        resp = await client.post(
            f"{BASE}/users/batch-delete",
            params={"user_ids": [real_user["id"], 999999999]},
            headers=_headers(admin_token),
        )
        assert resp.status_code == 404, f"含不存在 id 应 404，实际 {resp.status_code}"

        # 回滚验证：真实用户未被删除
        resp = await client.get(f"{BASE}/users/{real_user['id']}", headers=_headers(admin_token))
        assert resp.status_code == 200, "原子性被破坏：部分用户已被删除"

    async def test_batch_delete_self_forbidden(self, client: AsyncClient, admin_token: str):
        """AC-11：批量删除不得包含操作者自己"""
        resp = await client.get(
            f"{BASE}/users", params={"keyword": SUPER_ADMIN["phone"]}, headers=_headers(admin_token)
        )
        self_id = next(
            u["id"] for u in resp.json()["data"]["items"] if u["phone"] == SUPER_ADMIN["phone"]
        )

        other = await _create_user(client, admin_token)
        resp = await client.post(
            f"{BASE}/users/batch-delete",
            params={"user_ids": [other["id"], self_id]},
            headers=_headers(admin_token),
        )
        assert resp.status_code == 400, f"含自己应 400，实际 {resp.status_code}"
        assert "不能删除自己" in resp.json()["msg"]

        # 整体未生效
        resp = await client.get(f"{BASE}/users/{other['id']}", headers=_headers(admin_token))
        assert resp.status_code == 200

    async def test_public_stats_real(self, client: AsyncClient):
        """AC-12：public/stats 返回真实聚合（非硬编码 5000/200/1000/10000）"""
        resp = await client.get(f"{BASE}/public/stats", headers=TENANT_HEADERS)
        assert resp.status_code == 200, f"public/stats 失败: {resp.text}"
        data = resp.json()["data"]

        for key in ("total_students", "total_teachers", "total_classes", "total_bookings"):
            assert isinstance(data[key], int), f"{key} 应为整数"

        # 种子含 1 教师（13800138001）与 1 学员（13900139001）
        assert data["total_teachers"] >= 1
        assert data["total_students"] >= 1
