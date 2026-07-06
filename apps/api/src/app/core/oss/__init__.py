"""
OSS (Object Storage Service) - 对象存储服务模块

提供统一的文件上传接口，支持多种云存储后端：
- 阿里云 OSS
- AWS S3
- 腾讯云 COS
- 本地存储（开发环境）

功能特性：
- 统一接口设计（多态模式）
- 文件类型验证（白名单机制）
- 文件大小限制（可配置）
- 自动生成唯一文件名（防冲突）
- 支持图片压缩和缩略图生成
- 完整的错误处理和日志记录

使用示例：
    from app.core.oss import get_oss_service
    
    oss = get_oss_service()
    
    # 上传文件
    result = await oss.upload(file, "avatars/", allowed_types=["image/jpeg", "image/png"])
    
    # 删除文件
    await oss.delete("avatars/user_1001.jpg")
    
    # 生成预签名 URL（私有文件的临时访问链接）
    url = await oss.get_presigned_url("documents/contract.pdf", expires_in=3600)
"""

from .service import OSSService, get_oss_service, LocalStorageService, AliyunOSSService, UploadResult

__all__ = [
    "OSSService",
    "get_oss_service",
    "LocalStorageService",
    "AliyunOSSService",
    "UploadResult",
]