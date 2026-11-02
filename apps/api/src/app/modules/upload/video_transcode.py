"""视频编码规整：确保入库视频为小程序可直接播放的 H.264(AVC)。

背景：
- 微信小程序 ``<video>`` 及开发者工具模拟器无法解码 HEVC/H.265，
  从 iPhone 相册直接上传的视频常为 HEVC，会导致首页视频黑屏；
- 在入库前统一探测编码，非 H.264 的视频自动转码为
  ``H.264 + AAC + faststart`` 的 MP4，调用方拿到的 object_key 直接可播。

依赖：
- 运行环境需安装 ``ffmpeg`` / ``ffprobe``（Dockerfile 已安装）。
- 工具缺失时降级为不检查、原样保存，并记录告警，避免阻断上传链路。
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# 小程序端可直接播放的视频编码（avc1 为 MP4 中 H.264 的 codec tag）
PLAYABLE_CODECS: frozenset[str] = frozenset({"h264", "avc1"})

# 转码超时（秒）：200MB 的 HEVC 在小规格机器上转码可能较慢，留足余量
TRANSCODE_TIMEOUT_SECONDS = 600
PROBE_TIMEOUT_SECONDS = 60

_MIME_BY_EXT: dict[str, str] = {
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "webm": "video/webm",
}


def _mime_for(ext: str) -> str:
    return _MIME_BY_EXT.get(ext.lower(), "video/mp4")


def _tools_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


async def ensure_playable_h264(content: bytes, ext: str, mime: str) -> tuple[bytes, str, str]:
    """确保视频为 H.264；必要时自动转码为 MP4。

    Args:
        content: 原始视频字节
        ext: 原始扩展名（mp4/webm/mov）
        mime: 原始 MIME（客户端声明）

    Returns:
        (新内容, 扩展名, MIME)。未转码时原样返回；转码后统一为 ``mp4`` + ``video/mp4``。

    Raises:
        HTTPException: 转码失败或超时（400，提示改用 H.264 视频）
    """
    if not _tools_available():
        logger.warning(
            "[VideoTranscode] ffmpeg/ffprobe 不可用，跳过编码检查，"
            "若上传 HEVC 视频将无法在小程序播放（key 保持原样）"
        )
        return content, ext, mime

    tmp_dir = Path(tempfile.mkdtemp(prefix="video_transcode_"))
    src = tmp_dir / f"source.{ext or 'mp4'}"
    try:
        src.write_bytes(content)
        codec = await _probe_codec(src)
        if codec is None:
            # 探测失败（文件损坏/非标准容器）：不误伤，原样保存
            logger.warning("[VideoTranscode] 无法识别视频编码，按原文件保存")
            return content, ext, mime

        if codec in PLAYABLE_CODECS:
            return content, ext, mime

        logger.info("[VideoTranscode] 检测到编码 %s，自动转码为 H.264", codec)
        out = tmp_dir / "output.mp4"
        await _transcode(src, out)
        data = out.read_bytes()
        if not data:
            raise HTTPException(
                status_code=400,
                detail="视频转码失败：输出为空，请改用 H.264 编码的 MP4 上传",
            )
        logger.info(
            "[VideoTranscode] 转码完成：%s -> H.264，%.2fMB -> %.2fMB",
            codec,
            len(content) / 1024 / 1024,
            len(data) / 1024 / 1024,
        )
        return data, "mp4", "video/mp4"
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("[VideoTranscode] 转码异常: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="视频转码失败，请改用 H.264 编码的 MP4 上传",
        ) from exc
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def _probe_codec(path: Path) -> str | None:
    """用 ffprobe 读取首个视频流编码，失败返回 None."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name",
        "-of",
        "default=nw=1:nk=1",
        str(path),
    ]
    try:
        stdout = await _run(cmd, timeout=PROBE_TIMEOUT_SECONDS)
    except Exception as exc:
        logger.warning("[VideoTranscode] ffprobe 执行失败: %s", exc)
        return None
    lines = [line.strip().lower() for line in stdout.splitlines() if line.strip()]
    return lines[0] if lines else None


async def _transcode(src: Path, out: Path) -> None:
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(src),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        str(out),
    ]
    await _run(cmd, timeout=TRANSCODE_TIMEOUT_SECONDS)


async def _run(cmd: list[str], *, timeout: int) -> str:
    """执行子进程并返回 stdout；非零退出码或超时抛异常."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError:
        proc.kill()
        await proc.communicate()
        raise HTTPException(
            status_code=400,
            detail="视频处理超时，请上传体积更小或 H.264 编码的视频",
        ) from None

    if proc.returncode != 0:
        detail = stderr.decode("utf-8", errors="ignore").strip()[-300:]
        raise RuntimeError(f"命令执行失败({proc.returncode}): {detail}")
    return stdout.decode("utf-8", errors="ignore")
