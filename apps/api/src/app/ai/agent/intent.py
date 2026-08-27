"""
意图识别
职责：将用户自然语言转为结构化意图 + 提取参数

当前版本：关键词匹配 + 规则提取（无需 LLM）
后续版本：接入 LLM 进行语义理解，作为 fallback
"""

import re
from typing import Any


class IntentRecognizer:
    """
    意图识别器

    输入：用户自然语言
    输出：{"intent": "...", "confidence": 0.8, "params": {...}}
    """

    # 意图 → 关键词映射（按优先级排序）
    INTENTS = [
        ("cancel_booking",    ["取消", "退课", "退订", "不去了", "取消预约"]),
        ("create_booking",    ["预约", "报名", "我要上", "帮我约", "我想约", "预定"]),
        ("get_my_balance",    ["余额", "还剩多少", "课时余额", "还有多少课", "剩余课时"]),
        ("get_my_bookings",   ["我的预约", "我报了什么", "我的课", "预约记录", "报名记录"]),
        ("query_schedules",   ["排期", "明天", "今天", "这周", "下周", "时间表", "什么时候", "几点", "有什么课"]),
        ("query_courses",     ["课程", "有什么", "搜索", "找", "查"]),
    ]

    # 日期关键词提取
    DATE_PATTERNS = {
        "今天": 0,
        "明天": 1,
        "后天": 2,
    }

    def __init__(self):
        self._last_intent = None
        self._last_params = None

    def recognize(self, user_input: str) -> dict[str, Any]:
        """
        识别用户意图 + 提取参数

        Args:
            user_input: 用户输入，如 "帮我预约明天下午的瑜伽课"

        Returns:
            {
                "intent": "create_booking",
                "confidence": 0.8,
                "params": {
                    "keyword": "瑜伽",
                    "date": "2026-08-08",
                }
            }
        """
        user_input = user_input.strip()
        if not user_input:
            return {"intent": "unknown", "confidence": 0.0, "params": {}}

        # 1. 意图匹配
        intent, confidence = self._match_intent(user_input)

        # 2. 参数提取
        params = self._extract_params(user_input, intent)

        self._last_intent = intent
        self._last_params = params

        return {
            "intent": intent,
            "confidence": confidence,
            "params": params,
        }

    def _match_intent(self, text: str) -> tuple:
        """按优先级匹配意图"""
        for intent, keywords in self.INTENTS:
            for kw in keywords:
                if kw in text:
                    return intent, 0.8
        return "unknown", 0.0

    def _extract_params(self, text: str, intent: str) -> dict:
        """从文本中提取参数"""
        params = {}

        if intent in ("query_courses", "query_schedules", "create_booking"):
            kw = self._extract_course_keyword(text)
            if kw:
                params["keyword"] = kw

        if intent == "query_schedules":
            date = self._extract_date(text)
            if date:
                params["date"] = date

        if intent in ("get_my_bookings",):
            params["status"] = self._extract_booking_status(text)

        if intent == "cancel_booking":
            booking_id = self._extract_booking_id(text)
            if booking_id:
                params["booking_id"] = booking_id

        return params

    def _extract_course_keyword(self, text: str) -> str | None:
        """提取课程关键词"""
        course_keywords = ["瑜伽", "街舞", "芭蕾", "拉丁", "现代舞", "爵士", "中国舞", "普拉提"]
        for kw in course_keywords:
            if kw in text:
                return kw
        return None

    def _extract_date(self, text: str) -> str | None:
        """提取日期，返回 YYYY-MM-DD 格式"""
        from datetime import datetime, timedelta

        for word, offset in self.DATE_PATTERNS.items():
            if word in text:
                target = datetime.now() + timedelta(days=offset)
                return target.strftime("%Y-%m-%d")

        # 尝试匹配 YYYY-MM-DD 格式
        match = re.search(r"(\d{4}-\d{2}-\d{2})", text)
        if match:
            return match.group(1)

        return None

    def _extract_booking_status(self, text: str) -> str | None:
        """提取预约状态"""
        if any(w in text for w in ["已完成", "已上"]):
            return "completed"
        if any(w in text for w in ["已取消", "取消"]):
            return "cancelled"
        if any(w in text for w in ["未到", "缺席"]):
            return "no_show"
        return None  # 默认全部

    def _extract_booking_id(self, text: str) -> int | None:
        """提取预约 ID"""
        match = re.search(r"(\d{3,})", text)
        if match:
            return int(match.group(1))
        return None

    @property
    def last_intent(self) -> str | None:
        return self._last_intent
