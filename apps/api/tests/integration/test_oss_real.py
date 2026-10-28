"""真实 OSS 集成测试（S7）

仅当环境显式开启时运行，避免无凭证环境误报：
    OSS_IT_ENABLED=1 STORAGE_BACKEND=oss \
        OSS_CREDENTIALS_MODE=static OSS_ACCESS_KEY_ID=... OSS_ACCESS_KEY_SECRET=... \
        uv run pytest tests/integration/test_oss_real.py -v

所有对象写入专用前缀 ``t/{tenant_id}/_it/``，用例结束即删除，不触碰业务数据。
"""

import io
import os
import uuid

import alibabacloud_oss_v2 as oss
import httpx
import pytest

from app.core.config import get_settings
from app.core.oss_client import close_oss_client, get_oss_client, presign_object_url

settings = get_settings()

IT_ENABLED = os.getenv("OSS_IT_ENABLED") == "1" and settings.STORAGE_BACKEND == "oss"
IT_TENANT_ID = os.getenv("OSS_IT_TENANT_ID", "1")

pytestmark = pytest.mark.skipif(
    not IT_ENABLED,
    reason="真实 OSS 集成测试未启用（需 OSS_IT_ENABLED=1 且 STORAGE_BACKEND=oss）",
)


async def test_oss_put_presign_get_delete_roundtrip():
    """上传 → 预签名 → 下载校验 → 删除 → 链接失效。"""
    key = f"t/{IT_TENANT_ID}/_it/{uuid.uuid4().hex}.png"
    content = b"\x89PNG\r\n\x1a\n" + os.urandom(256)

    client = await get_oss_client(settings)
    try:
        await client.put_object(
            oss.models.PutObjectRequest(
                bucket=settings.OSS_BUCKET,
                key=key,
                body=io.BytesIO(content),
            )
        )

        url = await presign_object_url(key, expires_seconds=300, settings=settings)
        assert "Signature=" in url or "x-oss-signature" in url.lower()

        async with httpx.AsyncClient() as http:
            resp = await http.get(url)
            assert resp.status_code == 200, resp.text
            assert resp.content == content

        await client.delete_object(
            oss.models.DeleteObjectRequest(bucket=settings.OSS_BUCKET, key=key)
        )

        async with httpx.AsyncClient() as http:
            resp_after = await http.get(url)
            assert resp_after.status_code in (403, 404), resp_after.text
    finally:
        await close_oss_client()
