"""Tool Schema 派生与角色过滤单测（不依赖网络 / DB / Redis）。"""

import pytest

from app.ai.agent.tool_schema import (
    allowed_tool_names,
    build_openai_tools,
    validate_tool_specs,
)
from app.ai.mcp_server import TOOL_SPECS, ToolSpec

_READ_TOOL_NAMES = {"query_courses", "query_schedules", "get_my_bookings", "get_my_balance"}
_WRITE_TOOL_NAMES = {"create_booking", "cancel_booking"}


def test_validate_tool_specs_passes():
    validate_tool_specs()


def test_all_specs_properties_match_input_fields():
    assert set(TOOL_SPECS) == _READ_TOOL_NAMES | _WRITE_TOOL_NAMES

    for name, spec in TOOL_SPECS.items():
        properties = spec.parameters.get("properties", {})
        assert set(properties) == set(spec.input_fields), name
        assert spec.parameters.get("type") == "object", name
        assert spec.parameters.get("additionalProperties") is False, name
        assert spec.description, name


def test_no_identity_fields_in_schemas():
    forbidden = {"user_id", "tenant_id", "tenant_slug"}
    for spec in TOOL_SPECS.values():
        assert not (set(spec.parameters.get("properties", {})) & forbidden)


def test_build_openai_tools_structure_and_order():
    tools = build_openai_tools(["query_courses", "get_my_balance"])

    assert [t["function"]["name"] for t in tools] == ["query_courses", "get_my_balance"]
    assert tools[0]["type"] == "function"
    assert tools[0]["function"]["description"] == TOOL_SPECS["query_courses"].description
    assert tools[0]["function"]["parameters"] == TOOL_SPECS["query_courses"].parameters


def test_build_openai_tools_rejects_unknown_name():
    with pytest.raises(ValueError):
        build_openai_tools(["unknown_tool"])


def test_student_sees_four_readonly_tools():
    assert allowed_tool_names({"student"}, readonly_only=True) == _READ_TOOL_NAMES


def test_teacher_and_admin_have_no_balance_tool():
    expected = {"query_courses", "query_schedules", "get_my_bookings"}
    assert allowed_tool_names({"teacher"}, readonly_only=True) == expected
    assert allowed_tool_names({"admin"}, readonly_only=True) == expected
    assert allowed_tool_names({"super_admin"}, readonly_only=True) == expected


def test_no_role_sees_nothing():
    assert allowed_tool_names(set(), readonly_only=True) == set()
    assert allowed_tool_names(set(), readonly_only=False) == set()


def test_readonly_gate_hides_write_tools():
    for roles in ({"student"}, {"teacher"}, {"admin"}):
        assert not (allowed_tool_names(roles, readonly_only=True) & _WRITE_TOOL_NAMES)
    assert (
        allowed_tool_names({"student"}, readonly_only=False) == _READ_TOOL_NAMES | _WRITE_TOOL_NAMES
    )


def test_validate_rejects_properties_mismatch(monkeypatch):
    bad = ToolSpec(
        "bad_tool",
        "bad_tool",
        frozenset({"student"}),
        False,
        frozenset({"keyword"}),
        description="bad",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
    )
    monkeypatch.setitem(TOOL_SPECS, "bad_tool", bad)

    with pytest.raises(ValueError):
        validate_tool_specs()


def test_validate_rejects_identity_fields(monkeypatch):
    bad = ToolSpec(
        "bad_tool",
        "bad_tool",
        frozenset({"student"}),
        False,
        frozenset({"user_id"}),
        description="bad",
        parameters={
            "type": "object",
            "properties": {"user_id": {"type": "integer"}},
            "additionalProperties": False,
        },
    )
    monkeypatch.setitem(TOOL_SPECS, "bad_tool", bad)

    with pytest.raises(ValueError):
        validate_tool_specs()
