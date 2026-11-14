"""Tool Schema 派生：``TOOL_SPECS`` → OpenAI / 方舟 tools[]。

纯函数，无 IO：
  - ``TOOL_SPECS`` 始终是唯一 Tool 元数据源，这里只做投影与自检；
  - 角色过滤复用 ``required_roles``，不新建权限体系；
  - 身份字段（user_id / tenant_id / tenant_slug）永不出现在工具参数中。
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.ai.mcp_server import TOOL_SPECS

# 身份只能来自可信上下文，禁止由模型或前端传入
FORBIDDEN_IDENTITY_FIELDS = frozenset({"user_id", "tenant_id", "tenant_slug"})


def build_openai_tools(names: Iterable[str]) -> list[dict[str, Any]]:
    """按传入顺序把 Tool 名转换成 OpenAI function tools[] 结构。"""
    tools: list[dict[str, Any]] = []
    for name in names:
        spec = TOOL_SPECS.get(name)
        if spec is None:
            raise ValueError(f"未注册的 Tool: {name}")
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
        )
    return tools


def allowed_tool_names(
    role_codes: set[str] | frozenset[str],
    *,
    readonly_only: bool,
) -> set[str]:
    """按角色与只读闸门过滤工具名（required_roles 有交集即可见）。"""
    roles = set(role_codes)
    allowed: set[str] = set()
    for name, spec in TOOL_SPECS.items():
        if not (spec.required_roles & roles):
            continue
        if readonly_only and spec.is_write:
            continue
        allowed.add(name)
    return allowed


def validate_tool_specs() -> None:
    """自检：parameters.properties 必须与 input_fields 完全一致且不含身份字段。"""
    for name, spec in TOOL_SPECS.items():
        parameters = spec.parameters
        if not isinstance(parameters, dict):
            raise ValueError(f"Tool {name} 缺少 JSON Schema（parameters）")

        properties = parameters.get("properties")
        if not isinstance(properties, dict):
            raise ValueError(f"Tool {name} 的 parameters 缺少 properties")

        keys = set(properties)
        if keys != set(spec.input_fields):
            raise ValueError(
                f"Tool {name} 的 parameters.properties 与 input_fields 不一致："
                f"properties={sorted(keys)}, input_fields={sorted(spec.input_fields)}"
            )

        forbidden = keys & FORBIDDEN_IDENTITY_FIELDS
        if forbidden:
            raise ValueError(
                f"Tool {name} 的 parameters 不得包含身份字段: {', '.join(sorted(forbidden))}"
            )
