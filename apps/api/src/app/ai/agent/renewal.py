"""会员续费预警话术生成。

业务判定（到期 / 课时不足）由 Service 用代码完成；模型只允许把结构化结果
写成一句自然语言。任何模型失败（未启用 / 超时 / 异常）都退回模板。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.ai.llm.factory import get_llm_provider
from app.core.config import get_settings

logger = logging.getLogger(__name__)

RENEWAL_TITLE = "会员卡续费提醒"
MAX_CONTENT_CHARS = 200


def build_renewal_template(item: dict[str, Any]) -> str:
    """确定性模板：模型不可用时也必须能发出提醒。"""
    product = item.get("product_name") or "会员卡"
    days_left = item.get("days_left")
    remaining = item.get("remaining_credits")

    if days_left is not None:
        head = f"您的{product}将在 {days_left} 天后到期"
    else:
        head = f"您的{product}剩余课时不足"

    if remaining is not None:
        return f"{head}，当前剩余 {remaining} 课时，如需继续上课请及时续费。"
    return f"{head}，如需继续上课请及时续费。"


async def compose_renewal_content(item: dict[str, Any]) -> str:
    """优先调用 Provider 生成一句话；失败 / 超时 / 未启用时用模板兜底。"""
    template = build_renewal_template(item)
    settings = get_settings()
    if not settings.AI_LLM_ENABLED:
        return template

    prompt = (
        "请把下面这条会员卡提醒改写成一句简洁、礼貌的中文提醒，"
        "不超过 60 字，不得编造事实、不得承诺优惠：\n"
        f"学员：{item.get('student_name', '学员')}；"
        f"卡：{item.get('product_name', '会员卡')}；"
        f"剩余课时：{item.get('remaining_credits')}；"
        f"剩余天数：{item.get('days_left')}。"
    )

    try:
        response = await asyncio.wait_for(
            get_llm_provider().chat(
                messages=[
                    {"role": "system", "content": "你是舞蹈机构的课程顾问，只输出一句提醒。"},
                    {"role": "user", "content": prompt},
                ],
            ),
            timeout=settings.AI_LLM_TIMEOUT_MS / 1000,
        )
    except Exception as exc:  # noqa: BLE001 - 任何模型故障都退回模板
        logger.warning("[AI-RENEWAL] 话术生成失败，使用模板: error_type=%s", type(exc).__name__)
        return template

    content = (response.content or "").strip().replace("\n", " ")
    if not content or len(content) > MAX_CONTENT_CHARS:
        return template
    return content
