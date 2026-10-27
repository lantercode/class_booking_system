"""图片内容校验：真实格式识别、解码校验与像素上限。

与文件扩展名 / Content-Type 无关——这两者都由客户端提供、可伪造。
本模块以 Pillow 实际解码为准，同时防御「图片解压炸弹」（超大像素）。
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from PIL import Image, UnidentifiedImageError

# 单张图片允许的最大像素数（4000 万，约 8000x5000），防御解压炸弹
MAX_PIXELS = 40_000_000

# Pillow 官方格式名 → 存储扩展名（仅允许写入本项目的类型）
_FORMAT_TO_EXT: dict[str, str] = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
}


class ImageValidationError(ValueError):
    """图片内容不合规：无法解码、格式不支持或像素超限。"""


@dataclass(frozen=True)
class ImageInfo:
    """解码后得到的可信图片信息。"""

    extension: str
    width: int
    height: int

    @property
    def pixels(self) -> int:
        return self.width * self.height


def probe_image(content: bytes) -> ImageInfo:
    """解码图片并返回可信的格式与尺寸；不合规时抛 ImageValidationError。

    只做头部解析 + ``verify()``（不 ``load()`` 像素），因此不会真正解压整张图，
    内存开销可控；尺寸校验在解码前完成，可挡住超大像素文件。
    """
    try:
        with Image.open(BytesIO(content)) as image:
            fmt = (image.format or "").upper()
            width, height = image.size
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ImageValidationError("文件内容不是有效的图片（解码失败）") from exc

    extension = _FORMAT_TO_EXT.get(fmt)
    if extension is None:
        raise ImageValidationError(
            f"不支持的图片格式：{fmt or 'unknown'}；仅支持 JPEG / PNG / WEBP"
        )

    if width <= 0 or height <= 0:
        raise ImageValidationError("图片尺寸非法")

    info = ImageInfo(extension=extension, width=width, height=height)
    if info.pixels > MAX_PIXELS:
        raise ImageValidationError(
            f"图片像素过大（{width}x{height}），上限 {MAX_PIXELS} 像素"
        )

    return info


__all__ = ["MAX_PIXELS", "ImageInfo", "ImageValidationError", "probe_image"]
