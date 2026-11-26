#!/usr/bin/env python3
"""AI 对话 trace 日志聚合脚本（P1-1）。

从 ``docker logs`` 输出中解析 ``ai_chat_trace`` 日志行，输出 Markdown 统计表格：
模式分布、回退率、延迟分位、工具调用次数与 Token 粗估。

用法::

    docker logs --since 24h dance-api 2>&1 | grep ai_chat_trace > /tmp/trace.log
    .venv/bin/python scripts/ai_trace_stats.py /tmp/trace.log

    # 过滤示例：只看租户 1 的 llm 模式，取最近 7 天
    docker logs -t --since 7d dance-api 2>&1 | \\
        .venv/bin/python scripts/ai_trace_stats.py - --tenant 1 --mode llm --since 7d

设计约束（按 P1-1 风险项）：
- 日志格式变更时不得崩溃：缺失字段跳过并计数，非法 JSON 单独计数；
- 时间窗过滤依赖日志行前缀时间戳（需 ``docker logs -t``），无时间戳的行在
  指定 ``--since`` 时计为 ``no_timestamp`` 并排除，而不是静默丢弃。
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

TRACE_MARKER = "ai_chat_trace"

# 输入 Token 粗估：中文 1 字约 0.6~1 token，英文约 4 字符 / token。
# 取 1.5 字符/token 作为保守中值，仅用于横向对比，不作为计费依据。
CHARS_PER_TOKEN = 1.5

_SINCE_RE = re.compile(r"^(\d+)([mdh])$")
_TS_RE = re.compile(r"^\[?(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)")

MODE_ORDER = ("llm", "llm_fallback", "rule")


def parse_since(raw: str | None) -> timedelta | None:
    """解析 ``24h`` / ``7d`` / ``30m`` 形式的时间窗。"""
    if not raw:
        return None
    match = _SINCE_RE.match(raw.strip())
    if not match:
        raise argparse.ArgumentTypeError("时间窗格式应为 24h / 7d / 30m")
    value, unit = int(match.group(1)), match.group(2)
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    return timedelta(days=value)


def parse_timestamp(line: str) -> datetime | None:
    """从日志行前缀解析时间戳（``docker logs -t`` 才有）。"""
    match = _TS_RE.match(line)
    if not match:
        return None
    raw = match.group(1).replace(" ", "T")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def parse_trace(line: str) -> dict | None:
    """提取一行中的 trace JSON；不含标记返回 None，含标记但解析失败返回空 dict。"""
    idx = line.find(TRACE_MARKER)
    if idx < 0:
        return None
    payload = line[idx + len(TRACE_MARKER):]
    brace = payload.find("{")
    if brace < 0:
        return {}
    try:
        data = json.loads(payload[brace:].strip())
    except (json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def percentile(values: list[float], pct: float) -> float | None:
    """线性插值分位数；空列表返回 None。"""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = (len(ordered) - 1) * pct / 100
    lower, upper = math.floor(pos), math.ceil(pos)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (pos - lower)


def _fmt_ms(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f}"


def _fmt_pct(part: int, total: int) -> str:
    return "-" if total == 0 else f"{part / total * 100:.1f}%"


def aggregate(rows: list[dict], *, top_tools: int) -> dict:
    """把 trace 行聚合成统计结果。"""
    total = len(rows)
    modes = Counter(str(row.get("mode") or "unknown") for row in rows)
    statuses = Counter(str(row.get("status") or "unknown") for row in rows)

    latencies = [
        float(row["latency_ms"])
        for row in rows
        if isinstance(row.get("latency_ms"), (int, float))
    ]
    llm_calls = [
        int(row["llm_calls"])
        for row in rows
        if isinstance(row.get("llm_calls"), (int, float))
    ]
    tool_counts = [len(row["tools"]) for row in rows if isinstance(row.get("tools"), list)]
    input_chars = [
        int(row["input_length"])
        for row in rows
        if isinstance(row.get("input_length"), (int, float))
    ]

    tool_names: Counter[str] = Counter()
    for row in rows:
        tools = row.get("tools")
        if isinstance(tools, list):
            tool_names.update(str(name) for name in tools)

    step_values: dict[str, list[float]] = {}
    for row in rows:
        steps = row.get("step_ms")
        if not isinstance(steps, dict):
            continue
        for name, cost in steps.items():
            if isinstance(cost, (int, float)):
                step_values.setdefault(str(name), []).append(float(cost))

    fallback_reasons = Counter(
        str(row["fallback_reason"])
        for row in rows
        if row.get("fallback_reason")
    )

    return {
        "total": total,
        "modes": modes,
        "statuses": statuses,
        "latency_p50": percentile(latencies, 50),
        "latency_p95": percentile(latencies, 95),
        "latency_max": max(latencies) if latencies else None,
        "latency_samples": len(latencies),
        "avg_llm_calls": (sum(llm_calls) / len(llm_calls)) if llm_calls else None,
        "avg_tool_calls": (sum(tool_counts) / len(tool_counts)) if tool_counts else None,
        "tool_total": sum(tool_counts),
        "input_chars": sum(input_chars),
        "estimated_tokens": round(sum(input_chars) / CHARS_PER_TOKEN) if input_chars else 0,
        "top_tools": tool_names.most_common(top_tools),
        "steps": step_values,
        "fallback_reasons": fallback_reasons,
    }


def render_markdown(stats: dict, meta: dict) -> str:
    total = stats["total"]
    modes, statuses = stats["modes"], stats["statuses"]
    lines: list[str] = ["## AI 对话统计", ""]

    lines.append("| 指标 | 值 |")
    lines.append("|---|---|")
    lines.append(f"| trace 行数 | {total} |")
    lines.append(f"| 时间窗 | {meta['since_text']} |")
    lines.append(f"| 租户过滤 | {meta['tenant_text']} |")
    lines.append(f"| 模式过滤 | {meta['mode_text']} |")
    lines.append(
        f"| 解析失败 / 缺时间戳 / 被过滤 | "
        f"{meta['invalid']} / {meta['no_timestamp']} / {meta['filtered']} |"
    )
    lines.append(f"| 成功率 | {_fmt_pct(statuses.get('success', 0), total)} |")
    lines.append(f"| LLM 覆盖率 | {_fmt_pct(modes.get('llm', 0) + modes.get('llm_fallback', 0), total)} |")
    lines.append(f"| LLM 回退率 | {_fmt_pct(modes.get('llm_fallback', 0), total)} |")
    lines.append(f"| 延迟 P50 / P95 / Max (ms) | {_fmt_ms(stats['latency_p50'])} / "
                 f"{_fmt_ms(stats['latency_p95'])} / {_fmt_ms(stats['latency_max'])} |")
    lines.append(f"| 有延迟样本数 | {stats['latency_samples']} |")
    avg_llm = stats["avg_llm_calls"]
    avg_tool = stats["avg_tool_calls"]
    lines.append(f"| 平均 LLM 调用次数 | {'-' if avg_llm is None else f'{avg_llm:.2f}'} |")
    lines.append(f"| 平均工具调用次数 | {'-' if avg_tool is None else f'{avg_tool:.2f}'} |")
    lines.append(f"| 工具调用总数 | {stats['tool_total']} |")
    lines.append(
        f"| 输入字符数 / Token 粗估 | {stats['input_chars']} / {stats['estimated_tokens']} |"
    )
    lines.append("")

    lines.append("### 模式分布")
    lines.append("")
    lines.append("| mode | 次数 | 占比 |")
    lines.append("|---|---|---|")
    for mode in MODE_ORDER:
        if modes.get(mode):
            lines.append(f"| {mode} | {modes[mode]} | {_fmt_pct(modes[mode], total)} |")
    for mode, count in modes.items():
        if mode not in MODE_ORDER:
            lines.append(f"| {mode} | {count} | {_fmt_pct(count, total)} |")
    lines.append("")

    if stats["fallback_reasons"]:
        lines.append("### 回退原因")
        lines.append("")
        lines.append("| reason | 次数 |")
        lines.append("|---|---|")
        for reason, count in stats["fallback_reasons"].most_common():
            lines.append(f"| {reason} | {count} |")
        lines.append("")

    if stats["top_tools"]:
        lines.append("### 工具调用 Top")
        lines.append("")
        lines.append("| tool | 次数 |")
        lines.append("|---|---|")
        for name, count in stats["top_tools"]:
            lines.append(f"| {name} | {count} |")
        lines.append("")

    if stats["steps"]:
        lines.append("### 分步耗时（ms）")
        lines.append("")
        lines.append("| step | 样本 | P50 | P95 |")
        lines.append("|---|---|---|---|")
        for name, values in stats["steps"].items():
            lines.append(
                f"| {name} | {len(values)} | {_fmt_ms(percentile(values, 50))} | "
                f"{_fmt_ms(percentile(values, 95))} |"
            )
        lines.append("")

    lines.append(f"> Token 为粗估（输入 {CHARS_PER_TOKEN} 字符/token，不含 system prompt 与工具结果）。")
    return "\n".join(lines)


def collect(
    source,
    *,
    since: timedelta | None,
    tenant: int | None,
    mode: str | None,
    now: datetime | None = None,
) -> tuple[list[dict], dict]:
    """按过滤条件收集 trace 行。"""
    now = now or datetime.now(UTC)
    cutoff = now - since if since else None
    rows: list[dict] = []
    invalid = no_timestamp = filtered = 0

    for line in source:
        trace = parse_trace(line)
        if trace is None:
            continue
        if not trace:
            invalid += 1
            continue
        if cutoff is not None:
            timestamp = parse_timestamp(line)
            if timestamp is None:
                no_timestamp += 1
                continue
            if timestamp < cutoff:
                continue
        if tenant is not None and trace.get("tenant_id") != tenant:
            filtered += 1
            continue
        if mode is not None and trace.get("mode") != mode:
            filtered += 1
            continue
        rows.append(trace)

    meta = {
        "invalid": invalid,
        "no_timestamp": no_timestamp,
        "filtered": filtered,
        "since_text": f"最近 {since}" if since else "全部",
        "tenant_text": str(tenant) if tenant is not None else "全部",
        "mode_text": mode or "全部",
    }
    return rows, meta


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="聚合 ai_chat_trace 日志并输出 Markdown 统计")
    parser.add_argument("logfile", nargs="?", default="-", help="日志文件路径，- 表示 stdin")
    parser.add_argument("--since", help="时间窗，如 24h / 7d / 30m（需日志行带时间戳）")
    parser.add_argument("--tenant", type=int, help="只统计指定 tenant_id")
    parser.add_argument("--mode", choices=MODE_ORDER, help="只统计指定模式")
    parser.add_argument("--top-tools", type=int, default=10, help="工具排行条数，默认 10")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        since = parse_since(args.since)
    except argparse.ArgumentTypeError as exc:
        print(f"参数错误: {exc}", file=sys.stderr)
        return 2

    if args.logfile == "-":
        rows, meta = collect(
            sys.stdin, since=since, tenant=args.tenant, mode=args.mode
        )
    else:
        path = Path(args.logfile)
        if not path.is_file():
            print(f"日志文件不存在: {path}", file=sys.stderr)
            return 2
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            rows, meta = collect(
                handle, since=since, tenant=args.tenant, mode=args.mode
            )

    if not rows:
        print("未匹配到 ai_chat_trace 记录", file=sys.stderr)
        print(
            f"（解析失败 {meta['invalid']} 行，缺时间戳 {meta['no_timestamp']} 行，"
            f"被过滤 {meta['filtered']} 行）",
            file=sys.stderr,
        )
        return 1

    meta["since_text"] = f"最近 {args.since}" if since else "全部"
    stats = aggregate(rows, top_tools=args.top_tools)
    print(render_markdown(stats, meta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
