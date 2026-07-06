"""
OSS Service - 对象存储服务核心实现

提供统一的文件上传、删除、预签名 URL 生成等接口。
支持多种存储后端（阿里云 OSS、AWS S3、本地存储）。
"""

import os
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, BinaryIO
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """文件上传结果"""
    success: bool
    url: Optional[str] = None
    key: Optional[str] = None
    filename: Optional[str] = None
    size: int = 0
    content_type: Optional[str] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "url": self.url,
            "key": self.key,
            "filename": self.filename,
            "size": self.size,
            "content_type": self.content_type,
            "error_message": self.error_message,
        }


class OSSService:
    """OSS 服务基类（抽象接口）"""
    
    async def upload(self, file: BinaryIO, path_prefix: str = "", *, filename=None, content_type=None, allowed_types=None, max_size_mb=10):
        raise NotImplementedError("子类必须实现 upload() 方法")
    
    async def delete(self, key: str) -> bool:
        raise NotImplementedError("子类必须实现 delete() 方法")
    
    async def get_url(self, key: str) -> str:
        raise NotImplementedError("子类必须实现 get_url() 方法")
    
    async def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        raise NotImplementedError("子类必须实现 get_presigned_url() 方法")


class LocalStorageService(OSSService):
    """本地存储服务（开发环境使用）"""
    
    def __init__(self, storage_path="./uploads", base_url="http://localhost:8000/uploads"):
        self.storage_path = Path(storage_path)
        self.base_url = base_url.rstrip("/")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"[Local Storage] 初始化成功: {self.storage_path}")
    
    def _generate_filename(self, original_filename=None) -> str:
        unique_id = str(uuid.uuid4()).replace("-", "")[:12]
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        extension = ""
        if original_filename and "." in original_filename:
            extension = "." + original_filename.rsplit(".", 1)[-1].lower()
        return f"{unique_id}_{timestamp}{extension}"
    
    def _validate_file(self, file, content_type, allowed_types, max_size_mb):
        if allowed_types and content_type and content_type not in allowed_types:
            raise ValueError(f"文件类型不允许: {content_type}")
        
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        
        max_size_bytes = max_size_mb * 1024 * 1024
        if size > max_size_bytes:
            raise ValueError(f"文件过大: {size/(1024*1024):.2f}MB > {max_size_mb}MB")
    
    async def upload(self, file, path_prefix="", *, filename=None, content_type=None, allowed_types=None, max_size_mb=10):
        try:
            self._validate_file(file, content_type, allowed_types, max_size_mb)
            
            unique_filename = self._generate_filename(filename)
            
            today = datetime.now().strftime("%Y/%m/%d")
            full_path_prefix = f"{path_prefix.rstrip('/')}/{today}" if path_prefix else today
            
            dir_path = self.storage_path / full_path_prefix
            dir_path.mkdir(parents=True, exist_ok=True)
            
            file_path = dir_path / unique_filename
            
            content = file.read()
            with open(file_path, "wb") as f:
                f.write(content)
            
            key = f"{full_path_prefix}/{unique_filename}"
            url = f"{self.base_url}/{key}"
            
            logger.info(f"[Local Storage] ✅ 上传成功: {key} ({len(content)} bytes)")
            
            return UploadResult(success=True, url=url, key=key, filename=unique_filename, size=len(content), content_type=content_type)
            
        except ValueError as e:
            logger.warning(f"[Local Storage] ❌ 文件验证失败: {e}")
            return UploadResult(success=False, error_message=str(e))
        except Exception as e:
            logger.error(f"[Local Storage] ❌ 上传失败: {e}", exc_info=True)
            return UploadResult(success=False, error_message=f"上传失败: {str(e)}")
    
    async def delete(self, key: str) -> bool:
        try:
            file_path = self.storage_path / key
            if not file_path.exists():
                return False
            file_path.unlink()
            logger.info(f"[Local Storage] ✅ 删除成功: {key}")
            return True
        except Exception as e:
            logger.error(f"[Local Storage] ❌ 删除失败 (key={key}): {e}")
            return False
    
    async def get_url(self, key: str) -> str:
        return f"{self.base_url}/{key}"
    
    async def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return await self.get_url(key)


class AliyunOSSService(OSSService):
    """阿里云 OSS 存储（生产环境推荐）"""
    
    def __init__(self, access_key_id, access_key_secret, endpoint, bucket_name, bucket_url):
        try:
            import oss2
            self.auth = oss2.Auth(access_key_id, access_key_secret)
            self.bucket = oss2.Bucket(self.auth, endpoint, bucket_name)
            self.bucket_name = bucket_name
            self.bucket_url = bucket_url.rstrip("/")
            logger.info(f"[Aliyun OSS] ✅ 初始化成功: {bucket_name}@{endpoint}")
        except ImportError:
            raise ImportError("请安装阿里云 OSS SDK: pip install oss2")
    
    async def upload(self, file, path_prefix="", *, filename=None, content_type=None, allowed_types=None, max_size_mb=10):
        try:
            import oss2
            
            file.seek(0, 2)
            size = file.tell()
            file.seek(0)
            
            if allowed_types and content_type and content_type not in allowed_types:
                return UploadResult(success=False, error_message=f"文件类型不允许: {content_type}")
            
            max_size_bytes = max_size_mb * 1024 * 1024
            if size > max_size_bytes:
                return UploadResult(success=False, error_message=f"文件过大")
            
            unique_id = str(uuid.uuid4())[:8]
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            extension = ""
            if filename and "." in filename:
                extension = "." + filename.rsplit(".", 1)[-1].lower()
            
            unique_filename = f"{unique_id}_{timestamp}{extension}"
            
            today = datetime.now().strftime("%Y/%m/%d")
            full_path_prefix = path_prefix.rstrip("/") if path_prefix else ""
            object_key = f"{full_path_prefix}/{today}/{unique_filename}" if full_path_prefix else f"{today}/{unique_filename}"
            
            result = self.bucket.put_object(object_key, file, headers={"Content-Type": content_type or ""})
            
            if result.status == 200:
                url = f"{self.bucket_url}/{object_key}"
                logger.info(f"[Aliyun OSS] ✅ 上传成功: {object_key} ({size} bytes)")
                return UploadResult(success=True, url=url, key=object_key, filename=unique_filename, size=size, content_type=content_type)
            else:
                return UploadResult(success=False, error_message=f"OSS 上传失败: HTTP {result.status}")
                
        except Exception as e:
            logger.error(f"[Aliyun OSS] ❌ 上传异常: {e}", exc_info=True)
            return UploadResult(success=False, error_message=f"上传异常: {str(e)}")
    
    async def delete(self, key: str) -> bool:
        try:
            result = self.bucket.delete_object(key)
            if result.status == 204 or result.status == 200:
                logger.info(f"[Aliyun OSS] ✅ 删除成功: {key}")
                return True
            return False
        except Exception as e:
            logger.error(f"[Aliyun OSS] ❌ 删除异常 (key={key}): {e}")
            return False
    
    async def get_url(self, key: str) -> str:
        return f"{self.bucket_url}/{key}"
    
    async def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        try:
            import oss2
            signed_url = self.bucket.sign_url('GET', key, expires_in)
            return signed_url
        except Exception as e:
            logger.error(f"[Aliyun OSS] ❌ 生成预签名 URL 失败: {e}")
            raise


def get_oss_service():
    """工厂函数：根据配置创建对应的 OSS 服务实例"""
    from app.core.config import get_settings
    
    settings = get_settings()
    provider = getattr(settings, 'OSS_PROVIDER', 'local').lower()
    
    if provider == 'local':
        storage_path = getattr(settings, 'LOCAL_STORAGE_PATH', './uploads')
        base_url = getattr(settings, 'LOCAL_STORAGE_URL_PREFIX', 'http://localhost:8000/uploads')
        return LocalStorageService(storage_path=storage_path, base_url=base_url)
    
    elif provider == 'aliyun':
        access_key_id = getattr(settings, 'ALIYUN_OSS_ACCESS_KEY_ID', '')
        access_key_secret = getattr(settings, 'ALIYUN_OSS_ACCESS_KEY_SECRET', '')
        endpoint = getattr(settings, 'ALIYUN_OSS_ENDPOINT', '')
        bucket_name = getattr(settings, 'ALIYUN_OSS_BUCKET_NAME', '')
        bucket_url = getattr(settings, 'ALIYUN_OSS_BUCKET_URL', '')
        
        if not all([access_key_id, access_key_secret, endpoint, bucket_name]):
            raise ValueError("阿里云 OSS 配置不完整！请检查环境变量：ALIYUN_OSS_ACCESS_KEY_ID 等")
        
        return AliyunOSSService(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            endpoint=endpoint,
            bucket_name=bucket_name,
            bucket_url=bucket_url,
        )
    
    else:
        raise ValueError(f"不支持的 OSS Provider: {provider}. 支持: local, aliyun")


ALLOWED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"]
ALLOWED_DOCUMENT_TYPES = ["application/pdf", "application/msword"]
ALLOWED_VIDEO_TYPES = ["video/mp4", "video/quicktime"]