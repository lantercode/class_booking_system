"""S8 历史迁移：本地存储文件迁移到阿里云 OSS + 改写 DB 中的 /uploads/ 前缀。

背景：
- S1 之前业务表图片字段存的是本地静态路径（``/uploads/{key}``）；
  S1 起统一改存 object_key（``t/{tenant_id}/{biz_type}/{uuid}.{ext}``）。
- 生产环境 STORAGE_BACKEND=oss，需把本地存量文件上传到 OSS，
  并把 DB 中残留的 ``/uploads/`` 前缀值改写为 object_key 语义。

数据来源：
- ``{PROJECT_ROOT}/.uploads/``（当前本地存储目录，object_key 命名空间）
- ``{apps/api}/uploads/``（更早的历史目录，旧格式路径，通常为孤儿文件）

用法（均在 apps/api 目录下执行）：
    uv run python scripts/migrate_uploads_to_oss.py                # dry-run（默认）
    uv run python scripts/migrate_uploads_to_oss.py --apply        # 实际上传 + 改写 DB
    uv run python scripts/migrate_uploads_to_oss.py --verify       # 抽样验证（预签名 GET 比对）
    uv run python scripts/migrate_uploads_to_oss.py --report out.json

选项：
    --apply                 实际执行上传与 DB 改写（缺省只输出报告）
    --verify [N]            抽样验证 N 个文件（默认 3）：预签名 GET 后按 sha256 与本地比对
    --legacy-key-prefix P   旧格式孤儿文件的迁移目标前缀（如 t/1/avatar/legacy）；
                            缺省不迁移旧格式文件，仅在报告中列出
    --report PATH           将 JSON 报告写入指定路径

前置条件：
    - STORAGE_BACKEND=oss 且 OSS_* 配置齐全（static AK 或 ECS RAM 角色）
    - PostgreSQL 可达（读 DATABASE_URL）

安全说明：
    - 上传为幂等覆盖写（已存在且校验通过则跳过），不删除本地文件
    - DB 改写仅在事务内对 ``/uploads/t/{tid}/...`` 形态执行，
      旧格式路径（如 ``/uploads/avatars/2026/...``）只报告、不自动改写
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import mimetypes
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # scripts -> apps/api -> apps -> repo root
API_ROOT = PROJECT_ROOT / "apps" / "api"
sys.path.insert(0, str(API_ROOT / "src"))

from app.core.config import get_settings  # noqa: E402
from app.core.oss_client import close_oss_client, get_oss_client, presign_object_url  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("migrate")

# 合法 object_key：t/{tenant_id}/{biz_type}/{name}
KEY_PATTERN = re.compile(r"^t/\d+/[a-z_]+/\S+$")

# 参与扫描的业务图片字段（表名 → 列名）
IMAGE_COLUMNS: list[tuple[str, str]] = [
    ("users", "avatar_url"),
    ("courses", "cover_url"),
    ("course_categories", "icon_url"),
    ("classrooms", "cover_image_url"),
]


@dataclass
class LocalFile:
    """本地待迁移文件。"""

    path: Path
    object_key: str
    size: int
    legacy: bool = False


@dataclass
class Report:
    """迁移报告（dry-run / apply / verify 共用）。"""

    mode: str
    local_files: list[dict] = field(default_factory=list)
    skipped_local: list[dict] = field(default_factory=list)
    db_rewrites: list[dict] = field(default_factory=list)
    db_manual: list[dict] = field(default_factory=list)
    db_stats: dict[str, int] = field(default_factory=dict)
    uploaded: list[str] = field(default_factory=list)
    upload_skipped_existing: list[str] = field(default_factory=list)
    upload_failed: list[dict] = field(default_factory=list)
    verify_results: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ============================================================
# 本地文件扫描
# ============================================================


def scan_local_files() -> tuple[list[LocalFile], list[LocalFile]]:
    """扫描本地存储目录，返回 (可迁移文件, 旧格式文件)。"""
    settings = get_settings()
    migratable: list[LocalFile] = []
    legacy: list[LocalFile] = []

    roots: list[tuple[Path, bool]] = [
        (Path(settings.LOCAL_UPLOAD_DIR), False),
        (API_ROOT / "uploads", True),
    ]
    for root, is_legacy in roots:
        if not root.exists():
            continue
        for f in sorted(p for p in root.rglob("*") if p.is_file()):
            rel = f.relative_to(root).as_posix()
            entry = LocalFile(path=f, object_key=rel, size=f.stat().st_size, legacy=is_legacy)
            if is_legacy or not KEY_PATTERN.match(rel):
                legacy.append(entry)
            else:
                migratable.append(entry)
    return migratable, legacy


# ============================================================
# DB 扫描与改写
# ============================================================


def _sync_dsn() -> str:
    """把 asyncpg 风格 DSN 转成 asyncpg 直连可用形态。"""
    dsn = get_settings().DATABASE_URL
    return dsn.replace("postgresql+asyncpg://", "postgresql://", 1)


async def scan_db() -> tuple[list[dict], list[dict], dict[str, int]]:
    """扫描业务表图片字段，返回 (改写计划, 需人工处理, 统计)。"""
    import asyncpg  # noqa: PLC0415 - 延迟导入

    rewrites: list[dict] = []
    manual: list[dict] = []
    stats: dict[str, int] = {}
    prefix = get_settings().LOCAL_UPLOAD_PUBLIC_URL_PREFIX.rstrip("/")
    like = f"{prefix}/%"

    conn = await asyncpg.connect(_sync_dsn())
    try:
        for table, col in IMAGE_COLUMNS:
            rows = await conn.fetch(
                f"SELECT id, {col} AS v FROM {table} WHERE {col} LIKE $1",  # noqa: S608 - 表名列名来自常量白名单
                like,
            )
            stats[f"{table}.{col}"] = len(rows)
            for r in rows:
                stripped = r["v"][len(prefix) + 1 :]
                if KEY_PATTERN.match(stripped):
                    rewrites.append({"table": table, "column": col, "id": r["id"], "from": r["v"], "to": stripped})
                else:
                    manual.append({"table": table, "column": col, "id": r["id"], "value": r["v"]})
    finally:
        await conn.close()
    return rewrites, manual, stats


async def apply_db_rewrites(rewrites: list[dict]) -> int:
    """在单事务内执行 DB 前缀改写，返回受影响行数。"""
    import asyncpg  # noqa: PLC0415

    if not rewrites:
        return 0
    conn = await asyncpg.connect(_sync_dsn())
    affected = 0
    try:
        async with conn.transaction():
            for item in rewrites:
                result = await conn.execute(
                    f"UPDATE {item['table']} SET {item['column']} = $1 "  # noqa: S608 - 表名列名来自常量白名单
                    "WHERE id = $2 AND " + item["column"] + " = $3",
                    item["to"],
                    item["id"],
                    item["from"],
                )
                affected += int(result.split()[-1])
    finally:
        await conn.close()
    return affected


# ============================================================
# OSS 上传与抽样验证
# ============================================================


def _guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


async def upload_to_oss(files: list[LocalFile], report: Report) -> None:
    """逐个上传本地文件到 OSS（已存在同名对象则跳过）。"""
    import alibabacloud_oss_v2 as oss  # noqa: PLC0415

    settings = get_settings()
    client = await get_oss_client(settings)
    for f in files:
        try:
            try:
                await client.head_object(
                    oss.models.HeadObjectRequest(bucket=settings.OSS_BUCKET, key=f.object_key)
                )
                report.upload_skipped_existing.append(f.object_key)
                continue
            except Exception:  # noqa: BLE001 - head 404 等异常一律走上传
                pass

            await client.put_object(
                oss.models.PutObjectRequest(
                    bucket=settings.OSS_BUCKET,
                    key=f.object_key,
                    content_type=_guess_mime(f.path),
                    body=f.path.read_bytes(),
                )
            )
            report.uploaded.append(f.object_key)
            log.info("  上传: %s (%d bytes)", f.object_key, f.size)
        except Exception as exc:  # noqa: BLE001
            report.upload_failed.append({"object_key": f.object_key, "error": str(exc)[:200]})
            log.error("  失败: %s -> %s", f.object_key, exc)


async def verify_samples(files: list[LocalFile], count: int, report: Report) -> None:
    """抽样验证：预签名 GET 下载后按 sha256 与本地文件比对。"""
    import httpx  # noqa: PLC0415

    sample = files[:count]
    for f in sample:
        entry: dict = {"object_key": f.object_key, "match": False}
        try:
            local_sha = hashlib.sha256(f.path.read_bytes()).hexdigest()
            url = await presign_object_url(f.object_key, expires_seconds=300)
            async with httpx.AsyncClient(timeout=30) as http:
                resp = await http.get(url)
            if resp.status_code == 200:
                remote_sha = hashlib.sha256(resp.content).hexdigest()
                entry["match"] = local_sha == remote_sha
                entry["local_sha256"] = local_sha
                entry["remote_sha256"] = remote_sha
            else:
                entry["error"] = f"HTTP {resp.status_code}"
        except Exception as exc:  # noqa: BLE001
            entry["error"] = str(exc)[:200]
        report.verify_results.append(entry)
        log.info("  %s %s", "PASS" if entry["match"] else "FAIL", f.object_key)


# ============================================================
# 主流程
# ============================================================


def _print_report(report: Report) -> None:
    print(f"\n===== OSS 历史迁移报告（{report.mode}）=====")
    print(f"\n[本地文件] 可迁移 {len(report.local_files)} 个：")
    for f in report.local_files:
        print(f"  {f['object_key']}  ({f['size']} bytes)")
    if report.skipped_local:
        print(f"\n[旧格式文件] {len(report.skipped_local)} 个（缺省不迁移，可用 --legacy-key-prefix 指定目标前缀）：")
        for f in report.skipped_local:
            print(f"  {f['object_key']}  ({f['size']} bytes)")
    print(f"\n[DB 引用统计] {json.dumps(report.db_stats, ensure_ascii=False)}")
    if report.db_rewrites:
        print(f"\n[DB 改写计划] {len(report.db_rewrites)} 处 /uploads/ 前缀：")
        for r in report.db_rewrites:
            print(f"  {r['table']}.{r['column']} id={r['id']}: {r['from']} -> {r['to']}")
    if report.db_manual:
        print(f"\n[需人工处理] {len(report.db_manual)} 处旧格式 DB 值（不自动改写）：")
        for r in report.db_manual:
            print(f"  {r['table']}.{r['column']} id={r['id']}: {r['value']}")
    if report.mode != "dry-run":
        print(f"\n[上传结果] 成功 {len(report.uploaded)} / 跳过(已存在) {len(report.upload_skipped_existing)} / 失败 {len(report.upload_failed)}")
        for e in report.upload_failed:
            print(f"  失败: {e['object_key']} -> {e['error']}")
        affected = report.db_stats.get("_rewrites_applied", 0)
        print(f"[DB 改写] 已执行 {affected} 处")
    if report.verify_results:
        ok = sum(1 for v in report.verify_results if v["match"])
        print(f"\n[抽样验证] {ok}/{len(report.verify_results)} 通过")
    if report.errors:
        print(f"\n[错误] {len(report.errors)} 条")
        for e in report.errors:
            print(f"  {e}")
    print()


async def main() -> int:
    parser = argparse.ArgumentParser(description="本地存储历史文件迁移到 OSS")
    parser.add_argument("--apply", action="store_true", help="实际执行上传与 DB 改写（缺省 dry-run）")
    parser.add_argument("--verify", nargs="?", const=3, type=int, metavar="N", help="抽样验证 N 个文件（默认 3）")
    parser.add_argument("--legacy-key-prefix", default="", help="旧格式孤儿文件的迁移目标前缀，如 t/1/avatar/legacy")
    parser.add_argument("--report", default="", help="将 JSON 报告写入指定路径")
    args = parser.parse_args()

    settings = get_settings()
    if args.apply and settings.STORAGE_BACKEND != "oss":
        print("错误：--apply 需要 STORAGE_BACKEND=oss（当前为 local），请先配置 OSS_* 环境变量")
        return 1
    if args.apply and settings.OSS_CREDENTIALS_MODE == "ecs_role":
        print("提示：ecs_role 模式依赖 ECS 实例元数据服务，请确认在已绑定角色的 ECS 上执行")

    report = Report(mode="apply" if args.apply else "dry-run")

    # 1. 扫描本地文件
    migratable, legacy = scan_local_files()
    report.local_files = [
        {"object_key": f.object_key, "size": f.size, "path": str(f.path)} for f in migratable
    ]
    report.skipped_local = [{"object_key": f.object_key, "size": f.size} for f in legacy]

    # 2. 扫描 DB
    rewrites, manual, stats = await scan_db()
    report.db_rewrites = rewrites
    report.db_manual = manual
    report.db_stats = stats

    # 3. 旧格式文件可选迁移
    legacy_targets: list[LocalFile] = []
    if args.legacy_key_prefix and legacy:
        prefix = args.legacy_key_prefix.strip("/")
        for f in legacy:
            f.object_key = f"{prefix}/{f.path.relative_to(API_ROOT / 'uploads').as_posix()}"
            legacy_targets.append(f)
        report.local_files.extend(
            {"object_key": f.object_key, "size": f.size, "path": str(f.path)} for f in legacy_targets
        )

    # 4. 上传 + DB 改写
    if args.apply:
        to_upload = migratable + legacy_targets
        if to_upload:
            log.info("开始上传 %d 个文件到 OSS（bucket=%s）...", len(to_upload), settings.OSS_BUCKET)
            await upload_to_oss(to_upload, report)
        applied = await apply_db_rewrites(rewrites)
        report.db_stats["_rewrites_applied"] = applied
    else:
        print("\n（dry-run 模式：未上传、未改写，加 --apply 执行）")

    # 5. 抽样验证
    if args.verify is not None:
        if settings.STORAGE_BACKEND != "oss":
            print("错误：--verify 需要 STORAGE_BACKEND=oss")
            return 1
        verify_pool = migratable + legacy_targets
        if verify_pool:
            log.info("抽样验证 %d 个文件...", min(args.verify, len(verify_pool)))
            await verify_samples(verify_pool, args.verify, report)
        else:
            print("没有可验证的本地文件")

    _print_report(report)

    if args.report:
        Path(args.report).write_text(
            json.dumps(report.__dict__, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"JSON 报告已写入: {args.report}")

    await close_oss_client()
    return 1 if report.errors or report.upload_failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
