"""
Upload Repository - 文件对象数据访问层

继承 TenantAwareRepository，所有查询自动注入 tenant_id 隔离。
"""

from app.core.base_repository import TenantAwareRepository
from app.modules.upload.models import FileObject


class FileObjectRepository(TenantAwareRepository[FileObject]):
    """file_objects 表 Repository。

    TenantAwareRepository.create() 会自动从 ContextVar 取 tenant_id 注入，
    上层 Service 调用时无需手动传 tenant_id。
    """

    model_class = FileObject
