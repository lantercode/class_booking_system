"""上传图片校验单元测试（不依赖 OSS / 数据库 / 网络）.

覆盖 S1 加固项：
- 实际解码校验（伪造扩展名 / 损坏文件 / 非图片内容）
- 仅允许 JPEG / PNG / WEBP
- 像素上限（解压炸弹）
- 按 biz_type 区分的大小上限

覆盖 S2 加固项：
- 业务表图片字段（object_key 语义）归属校验与 URL 归一化
"""

import io

import pytest
from PIL import Image
from pydantic import ValidationError
from starlette.datastructures import Headers, UploadFile

from app.core import tenant_context
from app.core.config import Settings
from app.core.exceptions import ValidationException
from app.modules.upload import image_probe, service
from app.modules.upload.image_probe import ImageValidationError, probe_image
from app.modules.upload.router import enforce_biz_type_permission
from app.modules.upload.service import normalize_object_key


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


# ============================================================
# normalize_object_key（S2：业务字段归属校验）
# ============================================================

TENANT_ID = 7
_OSS_SETTINGS = Settings(
    STORAGE_BACKEND="oss",
    OSS_ENDPOINT="oss-cn-shanghai.aliyuncs.com",
    OSS_REGION="cn-shanghai",
    OSS_BUCKET="class-booking-system-prod",
    OSS_CREDENTIALS_MODE="static",
    OSS_ACCESS_KEY_ID="test-ak",
    OSS_ACCESS_KEY_SECRET="test-sk",
)


@pytest.fixture
def tenant_ctx():
    token = tenant_context.tenant_id.set(TENANT_ID)
    yield TENANT_ID
    tenant_context.tenant_id.reset(token)


@pytest.fixture
def local_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = Settings(
        APP_ENV="development",
        STORAGE_BACKEND="local",
        LOCAL_UPLOAD_PUBLIC_URL_PREFIX="/uploads",
    )
    monkeypatch.setattr(service, "get_settings", lambda: settings)
    return settings


@pytest.fixture
def oss_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setattr(service, "get_settings", lambda: _OSS_SETTINGS)
    return _OSS_SETTINGS


def test_normalize_accepts_own_object_key(tenant_ctx, local_settings) -> None:
    key = "t/7/avatar/abc.png"
    assert normalize_object_key(key, ("avatar",)) == key


def test_normalize_accepts_and_strips_local_url(tenant_ctx, local_settings) -> None:
    """前端回传展示值（/uploads/...）也应归一化为 object_key，保证幂等。"""
    normalized = normalize_object_key("/uploads/t/7/avatar/abc.png", ("avatar",))
    assert normalized == "t/7/avatar/abc.png"


def test_normalize_accepts_and_strips_oss_presigned_url(tenant_ctx, oss_settings) -> None:
    url = (
        "https://class-booking-system-prod.oss-cn-shanghai.aliyuncs.com/"
        "t/7/avatar/abc.png?Expires=1&Signature=x"
    )
    assert normalize_object_key(url, ("avatar",)) == "t/7/avatar/abc.png"


def test_normalize_rejects_cross_tenant_key(tenant_ctx, local_settings) -> None:
    with pytest.raises(ValidationException):
        normalize_object_key("t/8/avatar/abc.png", ("avatar",))


def test_normalize_rejects_unexpected_biz_type(tenant_ctx, local_settings) -> None:
    with pytest.raises(ValidationException):
        normalize_object_key("t/7/course_cover/abc.png", ("avatar",))


def test_normalize_rejects_path_traversal(tenant_ctx, local_settings) -> None:
    with pytest.raises(ValidationException):
        normalize_object_key("t/7/avatar/../9/avatar/abc.png", ("avatar",))


def test_normalize_rejects_external_url_for_avatar(tenant_ctx, local_settings) -> None:
    with pytest.raises(ValidationException):
        normalize_object_key("https://evil.example.com/a.png", ("avatar",))


def test_normalize_allows_external_url_for_course_cover(tenant_ctx, local_settings) -> None:
    external = "https://cdn.example.com/cover.png"
    assert (
        normalize_object_key(
            external, ("course_cover",), allow_external_url=True
        )
        == external
    )


def test_normalize_requires_tenant_context(local_settings) -> None:
    with pytest.raises(ValidationException):
        normalize_object_key("t/7/avatar/abc.png", ("avatar",))


def test_normalize_empty_means_clear(tenant_ctx, local_settings) -> None:
    assert normalize_object_key("", ("avatar",)) is None
    assert normalize_object_key("   ", ("avatar",)) is None
    assert normalize_object_key(None, ("avatar",)) is None


# ============================================================
# biz_type 分级授权（S2）
# ============================================================


@pytest.mark.parametrize("role", ["student", "teacher"])
def test_avatar_upload_allowed_for_all_roles(role: str) -> None:
    enforce_biz_type_permission({role}, "avatar")


@pytest.mark.parametrize("role", ["admin", "super_admin"])
@pytest.mark.parametrize("biz_type", ["banner", "course_cover", "classroom_cover", "notice"])
def test_admin_can_upload_non_avatar(role: str, biz_type: str) -> None:
    enforce_biz_type_permission({role}, biz_type)


@pytest.mark.parametrize("role", ["student", "teacher"])
@pytest.mark.parametrize("biz_type", ["banner", "course_cover", "classroom_cover", "notice"])
def test_non_admin_cannot_upload_non_avatar(role: str, biz_type: str) -> None:
    from app.core.exceptions import PermissionException

    with pytest.raises(PermissionException):
        enforce_biz_type_permission({role}, biz_type)
