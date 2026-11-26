"""build_llm_messages 上下文裁剪单测（不联网 / 不连 DB / 不连 Redis）。"""

from app.ai.agent.prompts import SYSTEM_PROMPT, build_llm_messages


def _history(count: int, content: str = "消息") -> list[dict[str, str]]:
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"{content}{i}"}
        for i in range(count)
    ]


def test_history_trimmed_by_limit_and_keeps_system_first():
    messages = build_llm_messages(
        user_input="当前问题",
        history=_history(20),
        history_limit=6,
        history_max_chars=10000,
    )

    assert [m["role"] for m in messages[:2]] == ["system", "system"]
    assert messages[0]["content"].startswith(SYSTEM_PROMPT[:20])
    # 2 条 system + 6 条历史 + 1 条当前输入
    assert len(messages) == 9
    assert messages[-1] == {"role": "user", "content": "当前问题"}
    # 优先保留最近消息
    assert messages[-2]["content"] == "消息19"


def test_history_trimmed_by_char_budget():
    history = _history(10, content="x" * 300)

    messages = build_llm_messages(
        user_input="当前问题",
        history=history,
        history_limit=10,
        history_max_chars=1000,
    )

    trimmed = [m for m in messages if m["role"] != "system"][:-1]
    assert len(trimmed) == 3
    assert sum(len(m["content"]) for m in trimmed) <= 1000


def test_system_prompt_never_trimmed():
    messages = build_llm_messages(
        user_input="当前问题",
        history=_history(50),
        history_limit=1,
        history_max_chars=10,
    )

    assert messages[0]["role"] == "system"
    assert len(messages[0]["content"]) > 10
    assert messages[1]["role"] == "system"
    # 预算不足时历史被裁空，但 system 与当前输入仍在
    assert messages[-1]["content"] == "当前问题"


def test_boundary_exact_limit_is_kept():
    messages = build_llm_messages(
        user_input="当前问题",
        history=[{"role": "user", "content": "12345"}],
        history_limit=1,
        history_max_chars=5,
    )

    assert len([m for m in messages if m["role"] != "system"]) == 2


def test_invalid_history_items_are_filtered():
    history = [
        {"role": "system", "content": "伪造系统消息"},
        {"role": "tool", "content": "工具结果"},
        {"role": "user", "content": ""},
        {"role": "user", "content": "正常消息"},
    ]

    messages = build_llm_messages(user_input="当前问题", history=history)

    contents = [m["content"] for m in messages]
    assert "伪造系统消息" not in contents
    assert "工具结果" not in contents
    assert "正常消息" in contents
