"""
T02 测试配置 - 使用真实 HTTP 服务器进行集成测试

设计决策：
- 使用 httpx.AsyncClient + 真实 HTTP 服务器（而非 ASGITransport）
- 彻底解决 asyncpg/asyncio 事件循环冲突问题
- 更接近生产环境的测试方式
"""

import asyncio
import threading
import time

import pytest
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.security import hash_password
from app.main import app as fastapi_app
from app.modules.auth.models import Permission, Role, RolePermission
from app.modules.tenant.models import Tenant, TenantStatus
from app.modules.user.models import User, UserStatus

settings = get_settings()
TEST_DATABASE_URL = settings.DATABASE_URL

# 全局变量存储服务器信息
_server_thread = None
_server_url = None


@pytest.fixture(scope="session")
def event_loop():
    """Session 级别的事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    if not loop.is_closed():
        loop.close()


@pytest.fixture(scope="session", autouse=True)
async def ensure_redis_available():
    """检查 Redis 可用性"""
    client = None
    try:
        client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        result = await client.ping()
        assert result is True
        print("\n✅ Redis 连接正常")
    finally:
        if client:
            await client.close()


@pytest.fixture(scope="session", autouse=True)
async def seed_test_database():
    """Session 级别：在测试开始前初始化种子数据"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_size=3,
        max_overflow=5,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        try:
            # 检查是否已有种子数据
            result = await session.execute(select(Tenant).where(Tenant.slug == "dance-school"))
            existing_tenant = result.scalar_one_or_none()
            if existing_tenant:
                print("\n🌱 种子数据已存在，跳过初始化")
                yield
                return

            print("\n 开始初始化测试种子数据...")

            # 1. 创建默认租户
            tenant = Tenant(
                name="奕欣舞蹈",
                slug="dance-school",
                contact_phone="13800000001",
                status=TenantStatus.ACTIVE.value,
                plan="pro",
                settings={"theme": "default", "language": "zh-CN", "timezone": "Asia/Shanghai"},
            )
            session.add(tenant)
            await session.flush()
            print(f"  ✅ 创建租户: {tenant.name}")

            # 2. 创建系统角色
            roles_data = [
                {"code": "super_admin", "name": "超级管理员", "is_system": True, "description": "拥有所有权限"},
                {"code": "admin", "name": "管理员", "is_system": True, "description": "管理机构日常运营"},
                {"code": "teacher", "name": "老师", "is_system": False, "description": "授课老师"},
                {"code": "student", "name": "学员", "is_system": False, "description": "普通学员"},
            ]
            roles = []
            for rd in roles_data:
                role = Role(tenant_id=tenant.id, code=rd["code"], name=rd["name"],
                            is_system=rd["is_system"], description=rd["description"])
                session.add(role)
                roles.append(role)
            await session.flush()
            print(f"  ✅ 创建 {len(roles)} 个角色")

            # 3. 创建权限项
            permissions_data = [
                {"code": "course:create", "name": "创建课程", "module": "course"},
                {"code": "course:update", "name": "编辑课程", "module": "course"},
                {"code": "course:delete", "name": "删除课程", "module": "course"},
                {"code": "schedule:create", "name": "创建排课", "module": "schedule"},
                {"code": "schedule:update", "name": "编辑排课", "module": "schedule"},
                {"code": "schedule:cancel", "name": "取消排课", "module": "schedule"},
                {"code": "schedule:delete", "name": "删除排课", "module": "schedule"},
                {"code": "booking:view", "name": "查看预约", "module": "booking"},
                {"code": "booking:manage", "name": "管理预约", "module": "booking"},
                {"code": "user:create", "name": "创建用户", "module": "user"},
                {"code": "user:read", "name": "查看用户", "module": "user"},
                {"code": "user:update", "name": "编辑用户", "module": "user"},
                {"code": "user:delete", "name": "删除用户", "module": "user"},
                {"code": "user:manage", "name": "管理用户", "module": "user"},
                {"code": "user:reset_password", "name": "重置密码", "module": "user"},
                {"code": "classroom:create", "name": "创建教室", "module": "classroom"},
                {"code": "classroom:read", "name": "查看教室", "module": "classroom"},
                {"code": "classroom:update", "name": "编辑教室", "module": "classroom"},
                {"code": "classroom:delete", "name": "删除教室", "module": "classroom"},
                {"code": "role:create", "name": "创建角色", "module": "role"},
                {"code": "role:read", "name": "查看角色", "module": "role"},
                {"code": "role:update", "name": "编辑角色", "module": "role"},
                {"code": "role:delete", "name": "删除角色", "module": "role"},
                {"code": "role:assign", "name": "分配角色", "module": "role"},
                {"code": "role:read_permissions", "name": "查看角色权限", "module": "role"},
                {"code": "stats:view", "name": "查看统计", "module": "stats"},
            ]
            permissions = []
            for pd in permissions_data:
                perm = Permission(code=pd["code"], name=pd["name"], module=pd["module"])
                session.add(perm)
                permissions.append(perm)
            await session.flush()
            print(f"  ✅ 创建 {len(permissions)} 个权限")

            # 4. 分配权限给角色
            super_admin_role = next(r for r in roles if r.code == "super_admin")
            for perm in permissions:
                session.add(RolePermission(role_id=super_admin_role.id, permission_id=perm.id))

            admin_role = next(r for r in roles if r.code == "admin")
            admin_codes = {
                "course:create", "course:update",
                "schedule:create", "schedule:update", "schedule:cancel", "schedule:delete",
                "booking:view", "booking:manage",
                "user:create", "user:read", "user:update", "user:manage",
                "classroom:create", "classroom:read", "classroom:update",
                "role:read", "role:read_permissions", "role:assign",
                "stats:view",
            }
            for perm in permissions:
                if perm.code in admin_codes:
                    session.add(RolePermission(role_id=admin_role.id, permission_id=perm.id))

            teacher_role = next(r for r in roles if r.code == "teacher")
            teacher_codes = {
                "course:create", "course:update",
                "schedule:create", "schedule:update", "schedule:cancel",
                "booking:view", "booking:manage",
                "classroom:read",
            }
            for perm in permissions:
                if perm.code in teacher_codes:
                    session.add(RolePermission(role_id=teacher_role.id, permission_id=perm.id))

            student_role = next(r for r in roles if r.code == "student")
            student_perm = next(p for p in permissions if p.code == "booking:view")
            session.add(RolePermission(role_id=student_role.id, permission_id=student_perm.id))

            await session.flush()
            print("  ✅ 分配角色权限完成")

            # 5. 创建默认用户
            for phone, nickname, platform_role, role_code in [
                ("13800000001", "系统管理员", "super_admin", "super_admin"),
                ("13800138001", "张老师", "teacher", "teacher"),
                ("13900139001", "李同学", "student", "student"),
            ]:
                user = User(
                    tenant_id=tenant.id,
                    phone=phone,
                    password_hash=hash_password("Test@123456"),
                    nickname=nickname,
                    platform_role=platform_role,
                    status=UserStatus.ACTIVE.value,
                )
                session.add(user)
                await session.flush()
                target_role = next(r for r in roles if r.code == role_code)
                from app.modules.auth.models import UserRole
                session.add(UserRole(user_id=user.id, role_id=target_role.id))

            await session.commit()
            print("  🎉 测试种子数据初始化完成！")

        except Exception as e:
            await session.rollback()
            print(f"\n❌ 种子数据初始化失败: {e}")
            raise
        finally:
            await engine.dispose()

    yield


@pytest.fixture(scope="session")
def live_server(event_loop):
    """
    启动真实的 Uvicorn 服务器用于测试

    这是解决 asyncpg 事件循环冲突的根本方案：
    - 真实的服务器进程有自己的事件循环
    - 完全隔离于测试进程的事件循环
    - 避免 ASGITransport 的各种兼容性问题
    """
    global _server_thread, _server_url


    import uvicorn

    # 随机端口避免冲突
    port = 8765
    _server_url = f"http://127.0.0.1:{port}"

    # 在后台线程中启动服务器
    def run_server():
        config = uvicorn.Config(
            fastapi_app,
            host="127.0.0.1",
            port=port,
            log_level="warning",  # 减少日志输出
        )
        server = uvicorn.Server(config)
        server.run()

    _server_thread = threading.Thread(target=run_server, daemon=True)
    _server_thread.start()

    # 等待服务器启动
    max_wait = 5  # 最大等待 5 秒
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result == 0:
                print(f"\n🚀 测试服务器启动: {_server_url}")
                break
        except:
            pass
        time.sleep(0.1)
    else:
        raise RuntimeError(f"❌ 服务器在 {max_wait} 秒内未能启动")

    yield _server_url

    # 清理（daemon 线程会自动结束）
    _server_thread = None
    _server_url = None


@pytest.fixture(scope="function")
async def client(live_server):
    """
    Function 级别的 HTTP 客户端

    每个测试创建新的客户端连接到真实服务器
    """
    async with AsyncClient(base_url=live_server) as ac:
        yield ac


@pytest.fixture(scope="function")
async def db_session():
    """Function 级别的数据库会话 - 每个测试独立事务"""
    engine = None
    session = None

    try:
        engine = create_async_engine(
            TEST_DATABASE_URL,
            echo=False,
            pool_size=3,
            max_overflow=5,
            pool_pre_ping=True,
        )

        session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        session = session_factory()
        await session.begin()
        yield session

    finally:
        if session:
            try:
                await session.rollback()
            except Exception:
                pass
            finally:
                await session.close()

        if engine:
            try:
                await engine.dispose()
            except Exception:
                pass
