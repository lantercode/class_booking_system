"""上传图片校验单元测试（不依赖 OSS / 数据库 / 网络）.

覆盖 S1 加固项：
- 实际解码校验（伪造扩展名 / 损坏文件 / 非图片内容）
- 仅允许 JPEG / PNG / WEBP
- 像素上限（解压炸弹）
- 按 biz_type 区分的大小上限
"""

import io

import pytest
from PIL import Image
from pydantic import ValidationError
from starlette.datastructures import Headers, UploadFile

from app.core.config import Settings
from app.modules.upload import image_probe, service
from app.modules.upload.image_probe import ImageValidationError, probe_image


def _image_bytes(fmt: str = "PNG", size: tuple[int, int] = (64, 64)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 120, 60)).save(buffer, format=fmt)
    return buffer.getvalue()


def _upload(
    content: bytes,
    filename: str = "a.png",
    content_type: str = "image/png",
) -> UploadFile:
    return UploadFile(
        file=io.BytesIO(content),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


def _service() -> service.UploadService:
    # 仅测试校验逻辑，db 与存储层不参与
    return service.UploadService(db=None)  # type: ignore[arg-type]


# ============================================================
# probe_image
# ============================================================


@pytest.mark.parametrize(
    ("fmt", "expected_ext"),
    [("PNG", "png"), ("JPEG", "jpg"), ("WEBP", "webp")],
)
def test_probe_accepts_supported_formats(fmt: str, expected_ext: str) -> None:
    info = probe_image(_image_bytes(fmt))
    assert info.extension == expected_ext
    assert info.width == 64
    assert info.height == 64


def test_probe_rejects_non_image_bytes() -> None:
    with pytest.raises(ImageValidationError):
        probe_image(b"this is definitely not an image")


def test_probe_rejects_truncated_image() -> None:
    truncated = _image_bytes("PNG")[:40]
    with pytest.raises(ImageValidationError):
        probe_image(truncated)


def test_probe_rejects_gif() -> None:
    with pytest.raises(ImageValidationError):
        probe_image(_image_bytes("GIF"))


def test_probe_rejects_oversized_pixels(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(image_probe, "MAX_PIXELS", 100)
    with pytest.raises(ImageValidationError):
        probe_image(_image_bytes("PNG", size=(64, 64)))


# ============================================================
# UploadService._validate_and_read
# ============================================================


@pytest.mark.anyio
async def test_validate_and_read_returns_decoded_info() -> None:
    content = _image_bytes("PNG")
    data, info = await _service()._validate_and_read(_upload(content), "avatar")
    assert data == content
    assert info.extension == "png"


@pytest.mark.anyio
async def test_validate_and_read_rejects_disallowed_mime() -> None:
    upload = _upload(_image_bytes("PNG"), content_type="image/gif")
    with pytest.raises(Exception) as excinfo:
        await _service()._validate_and_read(upload, "avatar")
    assert "不支持的文件类型" in str(excinfo.value)


@pytest.mark.anyio
async def test_validate_and_read_rejects_disallowed_extension() -> None:
    upload = _upload(_image_bytes("PNG"), filename="payload.exe")
    with pytest.raises(Exception) as excinfo:
        await _service()._validate_and_read(upload, "avatar")
    assert "不支持的文件扩展名" in str(excinfo.value)


@pytest.mark.anyio
async def test_validate_and_read_rejects_fake_image() -> None:
    """扩展名与 MIME 都合法，但内容不是图片 —— 必须被解码校验拦住。"""
    upload = _upload(b"<?php echo 1; ?>" * 10, filename="a.png")
    with pytest.raises(Exception) as excinfo:
        await _service()._validate_and_read(upload, "avatar")
    assert "不是有效的图片" in str(excinfo.value)


@pytest.mark.anyio
async def test_validate_and_read_enforces_biz_type_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(service.MAX_SIZE_BY_BIZ, "avatar", 100)
    content = _image_bytes("PNG")
    assert len(content) > 100
    with pytest.raises(Exception) as excinfo:
        await _service()._validate_and_read(_upload(content), "avatar")
    assert "文件过大" in str(excinfo.value)


@pytest.mark.anyio
async def test_validate_and_read_rejects_empty_file() -> None:
    with pytest.raises(Exception) as excinfo:
        await _service()._validate_and_read(_upload(b""), "avatar")
    assert "文件内容为空" in str(excinfo.value)


def test_avatar_limit_is_stricter_than_cover() -> None:
    assert service.MAX_SIZE_BY_BIZ["avatar"] == 2 * 1024 * 1024
    assert service.MAX_SIZE_BY_BIZ["course_cover"] == 5 * 1024 * 1024


def test_validate_biz_type_rejects_unknown() -> None:
    with pytest.raises(Exception) as excinfo:
        service.UploadService._validate_biz_type("exe")
    assert "非法 biz_type" in str(excinfo.value)


# ============================================================
# 配置校验
# ============================================================


def test_presign_ttl_must_be_within_oss_limit() -> None:
    with pytest.raises(ValidationError):
        Settings(OSS_PRESIGN_TTL_SECONDS=10)

    with pytest.raises(ValidationError):
        Settings(OSS_PRESIGN_TTL_SECONDS=604801)


def test_presign_ttl_accepts_one_hour() -> None:
    settings = Settings(OSS_PRESIGN_TTL_SECONDS=3600)
    assert settings.OSS_PRESIGN_TTL_SECONDS == 3600
