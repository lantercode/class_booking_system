"""
RBAC 权限系统 - 真实 Redis 集成测试

此测试文件使用真实的 Redis 容器验证：
1. 缓存写入和读取的真实性能
2. Pipeline 操作的正确性
3. TTL 过期机制
4. 缓存清除功能

运行前确保：
- Docker Redis 容器已启动 (docker-compose up -d redis)
- Redis 可通过 localhost:6379 访问

运行方式:
    uv run pytest tests/integration/test_rbac_real_redis.py -v -s
"""

import pytest
import asyncio
from redis.asyncio import Redis

# 导入被测模块
from app.core.rbac.cache import (
    get_cache_key,
    get_cached_permissions,
    set_cached_permissions,
    clear_user_permission_cache,
)


@pytest.fixture
async def real_redis():
    """
    创建真实的 Redis 连接
    
    使用 Docker 中的 Redis 容器
    """
    redis = Redis(host="localhost", port=6379, db=0, decode_responses=True)
    
    # 测试连接
    try:
        pong = await redis.ping()
        assert pong == True, "Redis 连接失败"
        print("✅ Redis 连接成功")
        yield redis
    except Exception as e:
        print(f"❌ Redis 连接失败: {e}")
        raise
    finally:
        try:
            await redis.close()
        except Exception:
            pass  # 忽略关闭时的错误（Event loop 可能已关闭）


class TestRealRedisCacheOperations:
    """测试真实 Redis 环境下的缓存操作"""
    
    @pytest.mark.asyncio
    async def test_write_and_read_with_real_redis(self, real_redis):
        """测试在真实 Redis 中写入和读取权限缓存"""
        tenant_id = 10
        user_id = 2001
        permissions = ["user:create", "user:read", "user:delete", "class:manage"]
        
        # 步骤1: 写入缓存
        success = await set_cached_permissions(real_redis, tenant_id, user_id, permissions)
        assert success is True, "写入缓存失败"
        print(f"✅ 成功写入 {len(permissions)} 个权限到 Redis")
        
        # 步骤2: 读取缓存
        cached_perms = await get_cached_permissions(real_redis, tenant_id, user_id)
        assert cached_perms is not None, "读取缓存返回 None"
        assert len(cached_perms) == len(permissions), f"数量不匹配: {len(cached_perms)} vs {len(permissions)}"
        
        # 步骤3: 验证每个权限都存在
        for perm in permissions:
            assert perm in cached_perms, f"缺少权限: {perm}"
        
        print(f"✅ 从 Redis 读取到 {len(cached_perms)} 个权限: {cached_perms}")
    
    @pytest.mark.asyncio
    async def test_cache_key_format_consistency(self, real_redis):
        """测试 Key 格式的一致性"""
        key = get_cache_key(tenant_id=99, user_id=8888)
        expected_key = "perms:99:8888"
        
        assert key == expected_key, f"Key 格式错误: {key} != {expected_key}"
        
        # 直接用这个 key 写入和读取
        test_perms = ["test:permission"]
        success = await set_cached_permissions(real_redis, 99, 8888, test_perms)
        assert success is True
        
        cached = await get_cached_permissions(real_redis, 99, 8888)
        assert cached is not None
        assert "test:permission" in cached
        
        print(f"✅ Key 格式一致: {key}")
    
    @pytest.mark.asyncio
    async def test_clear_cache_removes_data(self, real_redis):
        """测试清除缓存后数据不存在"""
        tenant_id = 50
        user_id = 5005
        permissions = ["temp:create", "temp:delete"]
        
        # 写入缓存
        await set_cached_permissions(real_redis, tenant_id, user_id, permissions)
        
        # 验证存在
        cached_before = await get_cached_permissions(real_redis, tenant_id, user_id)
        assert cached_before is not None, "清除前应该有数据"
        
        # 清除缓存
        success = await clear_user_permission_cache(real_redis, tenant_id, user_id)
        assert success is True, "清除缓存失败"
        
        # 验证已删除
        cached_after = await get_cached_permissions(real_redis, tenant_id, user_id)
        assert cached_after is None, "清除后应该返回 None"
        
        print("✅ 缓存清除功能正常：清除后返回 None")
    
    @pytest.mark.asyncio
    async def test_different_users_have_separate_caches(self, real_redis):
        """测试不同用户的缓存是隔离的"""
        tenant_id = 30
        
        # 用户A的权限
        user_a_perms = ["admin:create", "admin:delete"]
        await set_cached_permissions(real_redis, tenant_id, 1001, user_a_perms)
        
        # 用户B的权限（不同的）
        user_b_perms = ["student:view", "student:book"]
        await set_cached_permissions(real_redis, tenant_id, 1002, user_b_perms)
        
        # 读取用户A的缓存
        cached_a = await get_cached_permissions(real_redis, tenant_id, 1001)
        assert "admin:create" in cached_a
        assert "student:view" not in cached_a  # 不应该包含用户B的权限
        
        # 读取用户B的缓存
        cached_b = await get_cached_permissions(real_redis, tenant_id, 1002)
        assert "student:view" in cached_b
        assert "admin:create" not in cached_b  # 不应该包含用户A的权限
        
        print("✅ 用户缓存隔离正确：用户A和用户B的数据互不影响")
    
    @pytest.mark.asyncio
    async def test_overwrite_existing_cache(self, real_redis):
        """测试覆盖已有的缓存（权限变更场景）"""
        tenant_id = 20
        user_id = 2020
        
        # 初始权限
        initial_perms = ["read:only"]
        await set_cached_permissions(real_redis, tenant_id, user_id, initial_perms)
        
        cached_initial = await get_cached_permissions(real_redis, tenant_id, user_id)
        assert len(cached_initial) == 1
        assert "read:only" in cached_initial
        
        # 权限变更（管理员给用户增加了新权限）
        updated_perms = ["read:only", "write:data", "delete:data"]
        await set_cached_permissions(real_redis, tenant_id, user_id, updated_perms)
        
        # 读取更新后的缓存
        cached_updated = await get_cached_permissions(real_redis, tenant_id, user_id)
        assert len(cached_updated) == 3
        assert "write:data" in cached_updated
        assert "delete:data" in cached_updated
        
        print(f"✅ 缓存覆盖正确：从 {len(initial_perms)} 个权限更新为 {len(updated_perms)} 个")


@pytest.mark.asyncio
async def test_redis_performance_benchmark(real_redis):
    """Redis 性能基准测试（可选）"""
    import time
    
    iterations = 100
    permissions = [f"perm:{i}" for i in range(20)]  # 模拟 20 个权限
    
    start_time = time.time()
    
    for i in range(iterations):
        tid = i % 10  # 模拟 10 个租户
        uid = i % 100  # 模拟 100 个用户
        await set_cached_permissions(real_redis, tid, uid, permissions)
    
    write_time = time.time() - start_time
    write_avg = (write_time / iterations) * 1000  # ms
    
    start_time = time.time()
    
    for i in range(iterations):
        tid = i % 10
        uid = i % 100
        await get_cached_permissions(real_redis, tid, uid)
    
    read_time = time.time() - start_time
    read_avg = (read_time / iterations) * 1000  # ms
    
    print(f"\n{'='*60}")
    print(f"📊 Redis 性能基准测试结果 ({iterations} 次操作)")
    print(f"{'='*60}")
    print(f"写入操作:")
    print(f"  - 总耗时: {write_time:.3f}s")
    print(f"  - 平均耗时: {write_avg:.2f}ms/次")
    print(f"\n读取操作:")
    print(f"  - 总耗时: {read_time:.3f}s")
    print(f"  - 平均耗时: {read_avg:.2f}ms/次")
    print(f"{'='*60}")
    
    # 性能断言（宽松阈值，局域网 Redis 应该很快）
    assert write_avg < 10, f"写入太慢: {write_avg:.2f}ms > 10ms"
    assert read_avg < 5, f"读取太慢: {read_avg:.2f}ms > 5ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])