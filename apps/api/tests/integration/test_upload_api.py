"""Upload 模块集成测试（S7）

覆盖场景：
1. 教师/学员可上传本人头像
2. 非管理员不可上传 banner / course_cover
3. 管理员可上传课程封面
4. 伪造图片、超限头像、未知 biz_type 被拒
5. 删除：本人可删、他人不可删、管理员可删、重复删 404
6. 跨租户 key 的删除与换链均 403
7. 头像字段伪造跨租户 key 被拒（400）
8. 课程封面保留外部 URL 能力；被课程引用的对象删除返回 409

运行命令：
    uv run pytest tests/integration/test_upload_api.py -v
"""

import io
import os
import re
import uuid

import pytest
from httpx import AsyncClient
from PIL import Image

BASE = "/api/v1"
TENANT_HEADERS = {"x-tenant-slug": "dance-school"}
SUPER_ADMIN = {"phone": "13800000001", "password": "Test@123456"}
SEED_TEACHER = {"phone": "13800138001", "password": "Test@123456"}
SEED_STUDENT = {"phone": "13900139001", "password": "Test@123456"}

OBJECT_KEY_PATTERN = re.compile(r"^t/\d+/[a-z_]+/[0-9a-f]{32}\.(png|jpg|webp)$")


async def _login(client: AsyncClient, account: dict) -> str:
    resp = await client.post(f"{BASE}/auth/login", json={"tenant_slug": "dance-school", **account})
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    body = resp.json()
    assert body["code"] == 0, f"登录业务失败: {body}"
    return body["data"]["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", **TENANT_HEADERS}


def _png_bytes(width: int = 32, height: int = 32, noisy: bool = False) -> bytes:
    """生成合法 PNG；noisy=True 用于构造超过头像 2MB 上限的图片。"""
    if noisy:
        image = Image.frombytes("RGB", (width, height), os.urandom(width * height * 3))
    else:
        image = Image.new("RGB", (width, height), (180, 160, 120))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


async def _upload(
    client: AsyncClient,
    token: str,
    biz_type: str = "avatar",
    *,
    content: bytes | None = None,
    filename: str = "avatar.png",
    mime: str = "image/png",
):
    return await client.post(
        f"{BASE}/upload/image",
        headers=_headers(token),
        files={"file": (filename, content if content is not None else _png_bytes(), mime)},
        data={"biz_type": biz_type},
    )


async def _upload_ok(client: AsyncClient, token: str, biz_type: str = "avatar") -> str:
    resp = await _upload(client, token, biz_type)
    assert resp.status_code == 200, f"上传失败: {resp.text}"
    body = resp.json()
    assert body["code"] == 0, body
    object_key = body["data"]["object_key"]
    assert OBJECT_KEY_PATTERN.match(object_key), object_key
    assert object_key.startswith(f"t/{body['data']['object_key'].split('/')[1]}/{biz_type}/")
    return object_key


async def _delete(client: AsyncClient, token: str, object_key: str):
    return await client.delete(f"{BASE}/upload/{object_key}", headers=_headers(token))


@pytest.fixture
async def admin_token(client: AsyncClient) -> str:
    return await _login(client, SUPER_ADMIN)


@pytest.fixture
async def teacher_token(client: AsyncClient) -> str:
    return await _login(client, SEED_TEACHER)


@pytest.fixture
async def student_token(client: AsyncClient) -> str:
    return await _login(client, SEED_STUDENT)


async def test_teacher_can_upload_avatar(client: AsyncClient, teacher_token: str):
    key = await _upload_ok(client, teacher_token, "avatar")
    assert "/avatar/" in key
    assert (await _delete(client, teacher_token, key)).status_code == 200


async def test_student_can_upload_avatar(client: AsyncClient, student_token: str):
    key = await _upload_ok(client, student_token, "avatar")
    assert (await _delete(client, student_token, key)).status_code == 200


async def test_teacher_cannot_upload_banner(client: AsyncClient, teacher_token: str):
    resp = await _upload(client, teacher_token, "banner")
    assert resp.status_code == 403, resp.text
    assert resp.json()["code"] != 0


async def test_admin_can_upload_course_cover(client: AsyncClient, admin_token: str):
    key = await _upload_ok(client, admin_token, "course_cover")
    assert (await _delete(client, admin_token, key)).status_code == 200


async def test_upload_rejects_fake_image(client: AsyncClient, teacher_token: str):
    resp = await _upload(client, teacher_token, "avatar", content=b"not an image")
    assert resp.status_code == 400, resp.text
    # 入参校验由路由/服务抛 HTTPException，响应体为 detail（非统一信封）
    body = resp.json()
    assert body.get("detail") or body.get("msg"), body


async def test_upload_rejects_oversized_avatar(client: AsyncClient, teacher_token: str):
    big = _png_bytes(1400, 1400, noisy=True)
    assert len(big) > 2 * 1024 * 1024
    resp = await _upload(client, teacher_token, "avatar", content=big)
    assert resp.status_code == 400, resp.text


async def test_upload_rejects_unknown_biz_type(client: AsyncClient, admin_token: str):
    resp = await _upload(client, admin_token, "hack_type")
    assert resp.status_code == 400, resp.text


async def test_delete_own_upload_then_repeat_returns_404(
    client: AsyncClient, teacher_token: str
):
    key = await _upload_ok(client, teacher_token, "avatar")
    first = await _delete(client, teacher_token, key)
    assert first.status_code == 200, first.text
    second = await _delete(client, teacher_token, key)
    assert second.status_code == 404, second.text


async def test_student_cannot_delete_teacher_file(
    client: AsyncClient, teacher_token: str, student_token: str
):
    key = await _upload_ok(client, teacher_token, "avatar")
    resp = await _delete(client, student_token, key)
    assert resp.status_code == 403, resp.text
    assert (await _delete(client, teacher_token, key)).status_code == 200


async def test_admin_can_delete_other_users_file(
    client: AsyncClient, admin_token: str, student_token: str
):
    key = await _upload_ok(client, student_token, "avatar")
    resp = await _delete(client, admin_token, key)
    assert resp.status_code == 200, resp.text


async def test_cross_tenant_key_forbidden(client: AsyncClient, teacher_token: str):
    fake_key = f"t/999999/avatar/{uuid.uuid4().hex}.png"
    resp = await _delete(client, teacher_token, fake_key)
    assert resp.status_code == 403, resp.text

    resp_url = await client.get(f"{BASE}/upload/url/{fake_key}", headers=_headers(teacher_token))
    assert resp_url.status_code == 403, resp_url.text


async def test_get_object_url_for_own_key(client: AsyncClient, teacher_token: str):
    key = await _upload_ok(client, teacher_token, "avatar")
    resp = await client.get(f"{BASE}/upload/url/{key}", headers=_headers(teacher_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"]["object_key"] == key
    assert body["data"]["url"]
    await _delete(client, teacher_token, key)


async def test_avatar_field_rejects_cross_tenant_key(client: AsyncClient, student_token: str):
    fake_key = f"t/999999/avatar/{uuid.uuid4().hex}.png"
    resp = await client.patch(
        f"{BASE}/auth/me",
        headers=_headers(student_token),
        json={"avatar": fake_key},
    )
    assert resp.status_code == 400, resp.text

    resp_external = await client.patch(
        f"{BASE}/auth/me",
        headers=_headers(student_token),
        json={"avatar": "https://evil.example.com/a.png"},
    )
    assert resp_external.status_code == 400, resp_external.text


async def _ensure_course_type(client: AsyncClient, token: str) -> str:
    """返回一个可用的课程类型 code（不存在时创建一个）。"""
    resp = await client.get(f"{BASE}/courses/types", headers=_headers(token))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    items = data.get("items", []) if isinstance(data, dict) else data
    if items:
        return items[0]["code"]

    code = f"it_{uuid.uuid4().hex[:6]}"
    created = await client.post(
        f"{BASE}/courses/types",
        headers=_headers(token),
        json={"name": f"集成测试类型-{code}", "code": code},
    )
    assert created.status_code == 201, created.text
    return code


async def test_course_cover_external_url_and_reference_protection(
    client: AsyncClient, admin_token: str
):
    """课程封面保留外部 URL；被课程引用的上传对象不允许删除（409）。"""
    key = await _upload_ok(client, admin_token, "course_cover")
    suffix = uuid.uuid4().hex[:8]
    type_code = await _ensure_course_type(client, admin_token)

    external = "https://cdn.example.com/cover.png"
    resp_external = await client.post(
        f"{BASE}/courses/",
        headers=_headers(admin_token),
        json={
            "name": f"外部封面课-{suffix}",
            "category": "中国舞",
            "course_type_code": type_code,
            "level": "初级",
            "cover_url": external,
        },
    )
    assert resp_external.status_code == 201, resp_external.text
    course_external_id = resp_external.json()["data"]["id"]
    assert resp_external.json()["data"]["cover_url"] == external

    resp_own = await client.post(
        f"{BASE}/courses/",
        headers=_headers(admin_token),
        json={
            "name": f"本地上传封面课-{suffix}",
            "category": "中国舞",
            "course_type_code": type_code,
            "level": "初级",
            "cover_url": key,
        },
    )
    assert resp_own.status_code == 201, resp_own.text
    course_own_id = resp_own.json()["data"]["id"]

    # 被课程引用时不允许删除
    blocked = await _delete(client, admin_token, key)
    assert blocked.status_code == 409, blocked.text

    # 解除引用（课程封面改为外部 URL）后即可删除
    # 注：课程删除为软删除，行仍持有 cover_url 引用，409 是预期产品语义
    resp_release = await client.patch(
        f"{BASE}/courses/{course_own_id}",
        headers=_headers(admin_token),
        json={"cover_url": external},
    )
    assert resp_release.status_code == 200, resp_release.text

    final = await _delete(client, admin_token, key)
    assert final.status_code == 200, final.text

    # 清理测试课程
    for course_id in (course_external_id, course_own_id):
        resp_del = await client.delete(
            f"{BASE}/courses/{course_id}", headers=_headers(admin_token)
        )
        assert resp_del.status_code == 200, resp_del.text
