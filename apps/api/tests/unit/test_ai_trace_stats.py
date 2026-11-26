"""P1-1 ai_trace_stats 解析与聚合的健壮性测试（不依赖数据库）。"""

import importlib.util
import io
import json
from datetime import UTC, datetime
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "ai_trace_stats.py"
_spec = importlib.util.spec_from_file_location("ai_trace_stats", _SCRIPT)
stats_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(stats_mod)


def _line(payload: dict, prefix: str | None = None) -> str:
    # 默认时间戳跟随当前时间，避免硬编码日期随真实时间推移超出 since 窗口
    if prefix is None:
        prefix = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ") + " INFO "
    return prefix + "ai_chat_trace " + json.dumps(payload, ensure_ascii=False)


def test_parse_trace_ignores_unrelated_and_tolerates_bad_json():
    assert stats_mod.parse_trace("INFO: 200 OK") is None
    assert stats_mod.parse_trace("ai_chat_trace {not json") == {}
    parsed = stats_mod.parse_trace(_line({"mode": "llm"}))
    assert parsed == {"mode": "llm"}


def test_collect_counts_invalid_and_filters():
    source = io.StringIO(
        "\n".join(
            [
                _line({"tenant_id": 1, "mode": "llm", "latency_ms": 100, "tools": []}),
                _line({"tenant_id": 2, "mode": "rule", "latency_ms": 50, "tools": []}),
                "ai_chat_trace {broken",
                "no trace here",
            ]
        )
    )
    rows, meta = stats_mod.collect(source, since=None, tenant=1, mode=None)
    assert len(rows) == 1
    assert rows[0]["tenant_id"] == 1
    assert meta["invalid"] == 1
    assert meta["filtered"] == 1


def test_collect_since_requires_timestamp():
    source = io.StringIO(
        "\n".join(
            [
                _line({"mode": "llm"}),
                _line({"mode": "llm"}, prefix="ai_chat_trace_prefix_without_ts "),
            ]
        )
    )
    rows, meta = stats_mod.collect(source, since=stats_mod.parse_since("24h"), tenant=None, mode=None)
    assert len(rows) == 1
    assert meta["no_timestamp"] == 1


def test_aggregate_handles_missing_fields():
    rows = [
        {"mode": "llm", "latency_ms": 100, "tools": ["a"], "step_ms": {"lock": 1}},
        {"mode": "llm_fallback", "fallback_reason": "timeout"},
        {},
    ]
    result = stats_mod.aggregate(rows, top_tools=3)
    assert result["total"] == 3
    assert result["latency_p50"] == 100
    assert result["avg_tool_calls"] == 1.0
    assert result["top_tools"] == [("a", 1)]
    assert result["fallback_reasons"]["timeout"] == 1
    markdown = stats_mod.render_markdown(
        result,
        {
            "invalid": 0,
            "no_timestamp": 0,
            "filtered": 0,
            "since_text": "全部",
            "tenant_text": "全部",
            "mode_text": "全部",
        },
    )
    assert "AI 对话统计" in markdown
    assert "unknown" in markdown or "回退原因" in markdown
