"""
基础设施组件集成测试

测试覆盖：
1. BaseRepository - 通用数据访问层
2. OSS Service - 文件上传服务
3. Rate Limiter - API 限流中间件
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from io import BytesIO

from app.core.base_repository import BaseRepository, TenantAwareRepository
from app.core.oss import get_oss_service, LocalStorageService, UploadResult
from app.middleware.rate_limiter import RateLimiter


class MockModel:
    """模拟的 SQLAlchemy Model"""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id')
        self.name = kwargs.get('name')
        self.tenant_id = kwargs.get('tenant_id')
        self.deleted_at = kwargs.get('deleted_at')
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestBaseRepository:
    """测试 BaseRepository 基础功能"""

    @pytest.fixture
    def repository(self):
        class TestRepo(BaseRepository[MockModel]):
            model_class = MockModel
        return TestRepo()

    @pytest.fixture
    def db_session(self):
        session = AsyncMock()
        session.execute = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        session.rollback = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_get_by_id_success(self, repository, db_session):
        expected_user = MockModel(id=1, name="张三", tenant_id=10)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = expected_user
        db_session.execute.return_value = mock_result
        
        result = await repository.get_by_id(db_session, id=1)
        
        assert result is not None
        assert result.id == 1
        assert result.name == "张三"
        print(f"✅ get_by_id 成功: id={result.id}, name={result.name}")

    @pytest.mark.asyncio
    async def test_create_record(self, repository, db_session):
        data = {"name": "李四", "tenant_id": 10}
        created_obj = await repository.create(db_session, data)
        
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()
        
        assert isinstance(created_obj, MockModel)
        print(f"✅ create 成功: name={created_obj.name}")

    @pytest.mark.asyncio
    async def test_update_record(self, repository, db_session):
        existing_obj = MockModel(id=1, name="旧名称")
        
        with patch.object(repository, 'get_by_id', return_value=existing_obj):
            result = await repository.update(db_session, id=1, data={"name": "新名称"})
            
            assert result is not None
            assert result.name == "新名称"
            print(f"✅ update 成功: name={result.name}")

    @pytest.mark.asyncio
    async def test_delete_soft(self, repository, db_session):
        existing_obj = MockModel(id=1, name="待删除")
        
        with patch.object(repository, 'get_by_id', return_value=existing_obj):
            success = await repository.delete(db_session, id=1)
            
            assert success is True
            assert existing_obj.deleted_at is not None
            print("✅ 软删除成功")

    @pytest.mark.asyncio
    async def test_exists_true(self, repository, db_session):
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        db_session.execute.return_value = mock_result
        
        exists = await repository.exists(db_session, filters={"phone": "13800138000"})
        assert exists is True
        print("✅ exists 返回 True")

    @pytest.mark.asyncio
    async def test_paginated_query(self, repository, db_session):
        items = [MockModel(id=i, name=f"用户{i}") for i in range(1, 6)]
        
        count_mock = MagicMock()
        count_mock.scalar.return_value = 100
        
        data_mock = MagicMock()
        data_mock.scalars.all.return_value = items
        
        db_session.execute.side_effect = [count_mock, data_mock]
        
        result_items, total = await repository.get_paginated(db_session, page=1, page_size=5)
        
        assert len(result_items) == 5
        assert total == 100
        print(f"✅ 分页查询: {len(result_items)} 条/页, 共 {total} 条")


class TestTenantAwareRepository:
    """测试多租户感知 Repository"""

    @pytest.mark.asyncio
    async def test_auto_inject_tenant_id_on_create(self):
        class UserRepo(TenantAwareRepository[MockModel]):
            model_class = MockModel
        
        repo = UserRepo()
        
        from app.core.tenant_context import set_tenant_id
        set_tenant_id(99)
        
        try:
            with patch.object(repo, '_get_tenant_id', return_value=99):
                db = AsyncMock()
                data = {"name": "租户用户"}
                result = await repo.create(db, data)
                
                assert result.tenant_id == 99
                print(f"✅ 自动注入 tenant_id={result.tenant_id}")
        finally:
            set_tenant_id(None)


class TestLocalStorageService:
    """测试本地存储服务"""

    @pytest.fixture
    def local_storage(self, tmp_path):
        return LocalStorageService(
            storage_path=str(tmp_path / "uploads"),
            base_url="http://localhost:8000/uploads"
        )

    @pytest.mark.asyncio
    async def test_upload_image(self, local_storage):
        file_content = b"fake image content"
        file_obj = BytesIO(file_content)
        
        result = await local_storage.upload(
            file_obj,
            path_prefix="avatars/",
            filename="profile.jpg",
            content_type="image/jpeg"
        )
        
        assert result.success is True
        assert result.url is not None
        print(f"✅ 上传成功: {result.url}, size={result.size} bytes")

    @pytest.mark.asyncio
    async def test_upload_invalid_type(self, local_storage):
        file_obj = BytesIO(b"malicious script")
        
        result = await local_storage.upload(
            file_obj,
            filename="virus.exe",
            content_type="application/x-executable",
            allowed_types=["image/jpeg"]
        )
        
        assert result.success is False
        assert "文件类型不允许" in result.error_message
        print(f"✅ 正确拒绝非法文件类型")

    @pytest.mark.asyncio
    async def test_upload_large_file(self, local_storage):
        large_content = b"x" * (11 * 1024 * 1024)
        file_obj = BytesIO(large_content)
        
        result = await local_storage.upload(
            file_obj,
            filename="large.bin",
            max_size_mb=10
        )
        
        assert result.success is False
        assert "文件过大" in result.error_message
        print("✅ 正确拒绝超大文件")

    @pytest.mark.asyncio
    async def test_delete_file(self, local_storage):
        file_obj = BytesIO(b"content to delete")
        upload_result = await local_storage.upload(file_obj, path_prefix="temp/")
        
        assert upload_result.success is True
        
        delete_success = await local_storage.delete(upload_result.key)
        assert delete_success is True
        print(f"✅ 删除成功: {upload_result.key}")


class TestRateLimiter:
    """测试限流器核心逻辑"""

    @pytest.fixture
    def limiter(self):
        return RateLimiter(redis_client=None, default_limit=3, default_window=60)

    @pytest.mark.asyncio
    async def test_allow_within_limit(self, limiter):
        for i in range(3):
            allowed, meta = await limiter.is_allowed(key="test_ip_1")
            assert allowed is True
        
        print("✅ 前 3 次请求全部通过")

    @pytest.mark.asyncio
    async def test_block_when_exceeded(self, limiter):
        for _ in range(3):
            await limiter.is_allowed(key="test_ip_2")
        
        allowed, meta = await limiter.is_allowed(key="test_ip_2")
        
        assert allowed is False
        assert meta["remaining"] == 0
        assert meta["retry_after"] > 0
        print(f"✅ 第 4 次被拒绝, retry_after={meta['retry_after']}s")

    @pytest.mark.asyncio
    async def test_different_keys_independent(self, limiter):
        for _ in range(3):
            await limiter.is_allowed(key="ip_A")
        
        allowed_a, _ = await limiter.is_allowed(key="ip_A")
        assert allowed_a is False
        
        allowed_b, _ = await limiter.is_allowed(key="ip_B")
        assert allowed_b is True
        
        print("✅ 不同 Key 的限流相互独立")


class TestInfrastructureIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """完整工作流：上传文件 + 限流保护"""
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            oss = LocalStorageService(storage_path=tmpdir, base_url="http://localhost:8000/uploads")
            
            file_obj = BytesIO(b"test document content")
            upload_result = await oss.upload(
                file_obj,
                path_prefix="documents/",
                filename="report.pdf",
                content_type="application/pdf"
            )
            
            assert upload_result.success is True
            
            limiter = RateLimiter(default_limit=2, default_window=60)
            
            allowed1, _ = await limiter.is_allowed(key="upload_test")
            allowed2, _ = await limiter.is_allowed(key="upload_test")
            allowed3, _ = await limiter.is_allowed(key="upload_test")
            
            assert allowed1 is True
            assert allowed2 is True
            assert allowed3 is False
            
            print("✅ 完整工作流测试通过：上传 + 限流")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])