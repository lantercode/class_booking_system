#!/usr/bin/env python3
"""测量火山方舟（Ark）首 token 延迟（TTFT）与端到端延迟。

用法：
    export ARK_API_KEY="你的key"
    apps/api/.venv/bin/python scripts/bench_ark_ttft.py
    apps/api/.venv/bin/python scripts/bench_ark_ttft.py --runs 30 --thinking disabled
    apps/api/.venv/bin/python scripts/bench_ark_ttft.py --with-tools --thinking both

说明：
    - 使用 stream=True，才能区分首 token 与整段生成完成。
    - 首 token 包含文本片段与 tool_calls 片段（function calling 场景）。
    - 只读调用，不写入文件，不打印 API Key。
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
from dataclasses import dataclass

import httpx

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seed-2-1-lite-260915"
DEFAULT_PROMPT = "帮我查一下这周有哪些舞蹈课"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "query_schedules",
            "description": "查询课程排期",
            "parameters": {
                "type": "object",
                "properties": {"date": {"type": "string", "description": "日期，格式 YYYY-MM-DD"}},
                "additionalProperties": False,
            },
        },
    }
]


@dataclass
class Sample:
    """单次请求的测量结果。"""

    ttft: float | None
    total: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    first_kind: str = ""
    error: str = ""


def percentile(values: list[float], p: float) -> float:
    """最近秩法计算百分位，p 取 0-100。"""
    ordered = sorted(values)
    index = max(0, math.ceil(p / 100 * len(ordered)) - 1)
    return ordered[index]


def measure(
    client: httpx.Client,
    url: str,
    model: str,
    prompt: str,
    thinking: str,
    with_tools: bool,
    max_tokens: int,
) -> Sample:
    payload: dict = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "max_tokens": max_tokens,
        "temperature": 0.3,
        "thinking": {"type": thinking},
        "stream_options": {"include_usage": True},
    }
    if with_tools:
        payload["tools"] = TOOLS

    start = time.perf_counter()
    ttft: float | None = None
    first_kind = ""
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    try:
        with client.stream("POST", url, json=payload) as response:
            if response.status_code != 200:
                response.read()
                return Sample(
                    ttft=None,
                    total=time.perf_counter() - start,
                    error=f"HTTP {response.status_code}: {response.text[:160]}",
                )
            for line in response.iter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data or data == "[DONE]":
                    continue
                chunk = json.loads(data)
                usage = chunk.get("usage") or {}
                if usage:
                    prompt_tokens = usage.get("prompt_tokens", prompt_tokens)
                    completion_tokens = usage.get("completion_tokens", completion_tokens)
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                if ttft is None:
                    if delta.get("tool_calls"):
                        ttft = time.perf_counter() - start
                        first_kind = "tool_calls"
                    elif delta.get("content"):
                        ttft = time.perf_counter() - start
                        first_kind = "content"
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        return Sample(
            ttft=None, total=time.perf_counter() - start, error=f"{type(exc).__name__}: {exc}"
        )

    return Sample(
        ttft=ttft,
        total=time.perf_counter() - start,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        first_kind=first_kind,
    )


def report(label: str, samples: list[Sample]) -> None:
    ok_samples = [s for s in samples if s.ttft is not None]
    failed = [s for s in samples if s.error]
    print(f"\n{label}")
    print(f"  样本 {len(samples)}  成功 {len(ok_samples)}  失败 {len(failed)}")
    for sample in failed[:3]:
        print(f"    ! {sample.error}")

    if not ok_samples:
        print("  无可统计数据")
        return

    ttfts = [s.ttft for s in ok_samples if s.ttft is not None]
    totals = [s.total for s in ok_samples]
    tool_hits = sum(1 for s in ok_samples if s.first_kind == "tool_calls")

    def row(name: str, values: list[float]) -> None:
        print(
            f"  {name}: p50={percentile(values, 50):.2f}s "
            f"p95={percentile(values, 95):.2f}s "
            f"p99={percentile(values, 99):.2f}s "
            f"max={max(values):.2f}s min={min(values):.2f}s "
            f"mean={statistics.fmean(values):.2f}s"
        )

    row("TTFT  ", ttfts)
    row("端到端", totals)

    prompt_tokens = [s.prompt_tokens for s in ok_samples if s.prompt_tokens is not None]
    completion_tokens = [s.completion_tokens for s in ok_samples if s.completion_tokens is not None]
    if prompt_tokens and completion_tokens:
        print(
            f"  tokens: 输入均值={statistics.fmean(prompt_tokens):.0f} "
            f"输出均值={statistics.fmean(completion_tokens):.0f}"
        )
    if tool_hits:
        print(f"  首个片段为 tool_calls 的次数: {tool_hits}")


def main() -> int:
    parser = argparse.ArgumentParser(description="测量火山方舟 TTFT 与端到端延迟")
    parser.add_argument("--runs", type=int, default=20, help="每个场景的请求次数，默认 20")
    parser.add_argument("--model", default=os.getenv("AI_LLM_MODEL", DEFAULT_MODEL))
    parser.add_argument("--base-url", default=os.getenv("AI_LLM_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument(
        "--thinking",
        choices=["disabled", "enabled", "both"],
        default="both",
        help="深度思考开关；both 会各跑一轮做对比",
    )
    parser.add_argument("--with-tools", action="store_true", help="请求中携带 tools")
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    api_key = os.getenv("ARK_API_KEY", "")
    if not api_key:
        print('缺少 ARK_API_KEY。请先执行： export ARK_API_KEY="你的key"', file=sys.stderr)
        return 2
    if args.runs < 1:
        print("--runs 必须大于 0", file=sys.stderr)
        return 2

    url = f"{args.base_url.rstrip('/')}/chat/completions"
    modes = ["disabled", "enabled"] if args.thinking == "both" else [args.thinking]

    print("\n火山方舟 TTFT 基准")
    print(f"  url      : {url}")
    print(f"  model    : {args.model}")
    print(f"  tools    : {'是' if args.with_tools else '否'}")
    print(f"  runs     : {args.runs} × {len(modes)} 场景")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    with httpx.Client(headers=headers, timeout=args.timeout) as client:
        for mode in modes:
            samples = [
                measure(
                    client=client,
                    url=url,
                    model=args.model,
                    prompt=args.prompt,
                    thinking=mode,
                    with_tools=args.with_tools,
                    max_tokens=args.max_tokens,
                )
                for _ in range(args.runs)
            ]
            label = f"thinking={mode}（{'带工具' if args.with_tools else '无工具'}）"
            report(label, samples)

    print("\n判读建议：")
    print("  TTFT p95 ≤ 1.5s → 单次模型超时 6s 合理，总预算 15s 够用")
    print("  TTFT p95 2-4s   → 单次超时调到 8s，总预算放宽到 20s")
    print("  TTFT p95 > 5s   → 先确认 thinking 已关闭，再考虑换模型")
    print("  带工具比无工具慢 2 倍以上 → 每轮最多 1 个 tool call")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
