"""
Agent 运行时核心
职责：对话循环、意图→Tool 调度、结果格式化

流程：
  用户输入 → IntentRecognizer → _execute_intent → Tool 函数 → 格式化回复
                                    ↑
                              SessionManager（上下文）
"""

import hashlib
import json
import logging
import time

from app.ai.agent.intent import IntentRecognizer
from app.ai.agent.prompts import build_system_messages as compose_system_messages
from app.ai.agent.session import SessionManager
from app.ai.mcp_server import (
    cancel_booking,
    create_booking,
    get_my_balance,
    get_my_bookings,
    query_courses,
    query_schedules,
)
from app.core.exceptions import BusinessException

# 意图 → 可用 Tool 映射（用于 system prompt 能力声明与 trace 记录）
INTENT_TOOL_MAP: dict[str, tuple[str, ...]] = {
    "query_courses": ("query_courses",),
    "query_schedules": ("query_schedules",),
    "get_my_bookings": ("get_my_bookings",),
    "get_my_balance": ("get_my_balance",),
    "create_booking": ("query_schedules", "create_booking"),
    "cancel_booking": ("cancel_booking",),
}


class AgentRuntime:
    """
    Agent 运行时

    负责完整的对话流程：
    1. 接收用户输入
    2. 识别意图 + 提取参数
    3. 调用对应的 Tool
    4. 格式化自然语言回复
    5. 管理会话上下文
    """

    def __init__(
        self,
        redis_client=None,
        user_id: int = None,
        tenant_id: int = None,
        role_id: int | None = None,
    ):
        self.intent = IntentRecognizer()
        self.session = SessionManager(redis_client, user_id=user_id)
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role_id = role_id
        # 当前请求的 system messages；当前无真实 LLM 调用点，仅供日志验证与 P2 适配层复用
        self.system_messages: list[dict[str, str]] = []
        self.logger = logging.getLogger(__name__)

    # ============================================================
    # System Prompt 组装（P2 LLM 适配层可直接复用）
    # ============================================================

    def build_system_messages(self) -> list[dict[str, str]]:
        """按当前可信上下文组装 system messages，不参与规则引擎识别逻辑。"""
        tools: list[str] = []
        for tool_names in INTENT_TOOL_MAP.values():
            tools.extend(tool_names)
        return compose_system_messages(
            user_id=self.user_id,
            tenant_id=self.tenant_id,
            role_id=self.role_id,
            available_tools=tools,
        )

    def _system_prompt_meta(self) -> dict:
        """只暴露长度与指纹，避免把系统提示词原文写入日志。"""
        joined = "\n".join(msg["content"] for msg in self.system_messages)
        return {
            "messages": len(self.system_messages),
            "chars": len(joined),
            "fingerprint": hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12],
        }

    async def chat(self, user_input: str, session_id: str = "default") -> str:
        """
        对话入口：处理用户输入，返回回复

        流程：
          1. 获取分布式锁（防止并发）
          2. 检查中间状态（多轮对话）
          3. 识别意图
          4. 调用对应 Tool
          5. 格式化结果返回
          6. 释放锁
        """
        started_at = time.perf_counter()
        trace = self._new_trace(session_id, user_input)
        # 当前无真实 LLM 调用点：每次请求组装 system messages，用于日志可验证性与 P2 复用
        self.system_messages = self.build_system_messages()
        trace["system_prompt"] = self._system_prompt_meta()

        lock_key = self.session._lock_scope_key(session_id)
        lock_acquired = False

        try:
            step_started = time.perf_counter()
            lock_acquired = await self._acquire_lock(lock_key)
            trace["step_ms"]["lock"] = self._elapsed_ms(step_started)

            if not lock_acquired:
                self.logger.warning(f"并发拦截: session={session_id}, 获取锁失败")
                trace["status"] = "business_error"
                trace["error"] = "concurrency_limited"
                return "⏳ 正在处理您的上一个请求，请稍候..."

            step_started = time.perf_counter()
            state = await self.session.get_state(session_id)
            trace["step_ms"]["state_read"] = self._elapsed_ms(step_started)
            if state:
                trace["intent"] = f"pending_state:{state.get('action')}"
                self.logger.info(
                    f"状态恢复: session={session_id}, action={state.get('action')}, "
                    f"input_length={len(user_input)}"
                )
                return await self._handle_pending_state(
                    user_input, session_id, state, trace=trace
                )

            user_input = user_input.strip()
            if not user_input:
                return "您好，请问有什么可以帮您？"

            step_started = time.perf_counter()
            await self.session.add_message(session_id, "user", user_input)
            trace["step_ms"]["history_write_user"] = self._elapsed_ms(step_started)

            step_started = time.perf_counter()
            result = self.intent.recognize(user_input)
            intent_name = result["intent"]
            params = result["params"]
            trace["intent"] = intent_name
            trace["step_ms"]["intent"] = self._elapsed_ms(step_started)

            self.logger.info(
                f"意图识别: session={session_id}, intent={intent_name}, params={params}"
            )

            if intent_name == "unknown":
                response = self._handle_unknown(user_input)
                self.logger.warning(
                    f"未知意图: session={session_id}, input_length={len(user_input)}"
                )
            else:
                response = await self._execute_intent(
                    intent_name, params, session_id, trace=trace
                )
                if trace["status"] == "success":
                    self.logger.info(f"Tool调用成功: session={session_id}, intent={intent_name}")

            step_started = time.perf_counter()
            await self.session.add_message(session_id, "assistant", response)
            trace["step_ms"]["history_write_assistant"] = self._elapsed_ms(step_started)

            return response

        except Exception as exc:
            # 兜底异常：记录 trace 后继续上抛，交由统一异常体系处理
            trace["status"] = "system_error"
            trace["error"] = type(exc).__name__
            self.logger.error(
                f"AI 对话未捕获异常: session={session_id}, error_type={type(exc).__name__}"
            )
            raise

        finally:
            trace["latency_ms"] = self._elapsed_ms(started_at)
            self._emit_trace(trace)
            if lock_acquired:
                await self._release_lock(lock_key)

    # ============================================================
    # 结构化 trace（只写日志，不落库、不影响业务结果）
    # ============================================================

    @staticmethod
    def _mask_session_id(session_id: str) -> str:
        """session_id 截断脱敏，避免日志过长。"""
        if not session_id:
            return ""
        if len(session_id) <= 16:
            return session_id
        return f"{session_id[:12]}..."

    def _new_trace(self, session_id: str, user_input: str) -> dict:
        return {
            "event": "ai_chat_trace",
            "session_id": self._mask_session_id(session_id),
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            # 不记录消息正文，只记录长度
            "input_length": len(user_input or ""),
            "intent": None,
            "tools": [],
            "step_ms": {},
            "latency_ms": None,
            "status": "success",
            "error": None,
        }

    def _emit_trace(self, trace: dict) -> None:
        try:
            self.logger.info(
                "ai_chat_trace %s",
                json.dumps(trace, ensure_ascii=False, separators=(",", ":")),
            )
        except Exception:
            # 日志失败不得影响业务结果
            pass

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return int((time.perf_counter() - started_at) * 1000)

    @staticmethod
    def _mark_error(trace: dict | None, status: str, exc: Exception) -> None:
        if trace is not None:
            trace["status"] = status
            trace["error"] = type(exc).__name__

    async def _call_tool(self, trace: dict | None, step: str, tool_name: str, awaitable):
        """执行 Tool 并记录名称与耗时（异常同样会记录，随后由上层判定状态）。"""
        started_at = time.perf_counter()
        try:
            return await awaitable
        finally:
            if trace is not None:
                trace["tools"].append(tool_name)
                trace["step_ms"][step] = self._elapsed_ms(started_at)

    async def _execute_intent(
        self,
        intent_name: str,
        params: dict,
        session_id: str = "default",
        trace: dict | None = None,
    ) -> str:
        """
        根据意图调用对应的 Tool 并格式化返回
        Tool 映射表：
          query_courses    → 搜索课程
          query_schedules  → 查询排期
          get_my_bookings  → 我的预约
          get_my_balance   → 课时余额
          create_booking   → 创建预约
          cancel_booking   → 取消预约
        """
        try:
            if intent_name == "query_courses":
                raw = await self._call_tool(
                    trace,
                    "tool_query_courses",
                    "query_courses",
                    query_courses(keyword=params.get("keyword", "")),
                )
                return self._format_courses(raw)

            elif intent_name == "query_schedules":
                raw = await self._call_tool(
                    trace,
                    "tool_query_schedules",
                    "query_schedules",
                    query_schedules(
                        date=params.get("date"),
                        keyword=params.get("keyword", ""),
                    ),
                )
                return self._format_schedules(raw)

            elif intent_name == "get_my_bookings":
                raw = await self._call_tool(
                    trace,
                    "tool_get_my_bookings",
                    "get_my_bookings",
                    get_my_bookings(
                        user_id=self.user_id,
                        status=params.get("status"),
                    ),
                )
                return self._format_bookings(raw)

            elif intent_name == "get_my_balance":
                raw = await self._call_tool(
                    trace,
                    "tool_get_my_balance",
                    "get_my_balance",
                    get_my_balance(user_id=self.user_id),
                )
                return self._format_balance(raw)

            elif intent_name == "create_booking":
                if not self.user_id:
                    return "请先登录后再预约课程"

                if "schedule_id" not in params:
                    raw = await self._call_tool(
                        trace,
                        "tool_query_schedules_for_booking",
                        "query_schedules",
                        query_schedules(
                            date=params.get("date"),
                            keyword=params.get("keyword", ""),
                        ),
                    )

                    schedules = self._parse_schedules(raw)

                    if not schedules:
                        return f"📅 没有找到符合条件的排期\n{raw}"

                    await self.session.set_state(
                        session_id,
                        {
                            "action": "selecting_schedule",
                            "schedules": schedules,
                            "keyword": params.get("keyword", ""),
                            "date": params.get("date"),
                        },
                    )

                    return self._format_schedule_options(schedules)

                raw = await self._call_tool(
                    trace,
                    "tool_create_booking",
                    "create_booking",
                    create_booking(
                        schedule_id=params["schedule_id"],
                        user_id=self.user_id,
                    ),
                )
                await self.session.clear_state(session_id)
                return self._format_booking_result(raw)

            elif intent_name == "cancel_booking":
                if not self.user_id:
                    return "请先登录后再取消预约"

                if "booking_id" not in params:
                    return "请告诉我您想取消哪个预约（例如：取消预约 1001）"

                state_data = {
                    "action": "confirming_cancel",
                    "booking_id": params["booking_id"],
                }

                await self.session.set_state(session_id, state_data)

                self.logger.info(
                    f"存入取消确认状态: session={session_id}, booking_id={params['booking_id']}"
                )

                verify_state = await self.session.get_state(session_id)
                self.logger.info(f"验证状态存储: session={session_id}, state={verify_state}")

                return (
                    f"⚠️ 您确定要取消预约 #{params['booking_id']} 吗？\n\n"
                    f"请回复：\n"
                    f'• "是" 或 "确认" → 执行取消\n'
                    f'• "否" 或 "取消" → 保留预约'
                )

            else:
                return self._handle_unknown(intent_name)

        except BusinessException as exc:
            self._mark_error(trace, "business_error", exc)
            return self._handle_business_error(exc)
        except Exception as exc:
            self._mark_error(trace, "system_error", exc)
            return self._handle_business_error(exc)

    async def _handle_pending_state(
        self, user_input: str, session_id: str, state: dict, trace: dict | None = None
    ):
        """
        处理多轮对话的中间状态

        场景示例：
          第1轮：用户说"帮我约瑜伽课"
                 → 查排期 → 存状态 {action: "selecting_schedule", schedules: [...]}
                 → 返回选项 [1] 14:00 王老师 / [2] 16:00 李老师

          第2轮：用户回复"1"
                 → 进入本方法 → 解析选择 → 调用 create_booking → 清除状态 → 返回结果
        """
        self.logger.info(
            f"处理中间状态: session={session_id}, action={state.get('action')}, "
            f"input_length={len(user_input)}"
        )

        if state["action"] == "selecting_schedule":
            schedules = state.get("schedules", [])

            selection = self._parse_user_selection(user_input, len(schedules))

            if selection is None:
                return (
                    f"❌ 无法识别您的选择「{user_input}」\n\n"
                    f'请回复数字，如 "1"、"2" 或 "第1个"\n\n'
                    f"{self._format_schedule_options(schedules)}"
                )

            selected_schedule = schedules[selection - 1]

            self.logger.info(
                f"用户选择排期: session={session_id}, selection={selection}, "
                f"schedule_id={selected_schedule['id']}"
            )

            try:
                raw = await self._call_tool(
                    trace,
                    "tool_create_booking_from_selection",
                    "create_booking",
                    create_booking(
                        user_id=self.user_id,
                        schedule_id=selected_schedule["id"],
                    ),
                )

                await self.session.clear_state(session_id)

                self.logger.info(
                    f"预约成功: session={session_id}, schedule_id={selected_schedule['id']}, "
                    f"user_id={self.user_id}"
                )

                return (
                    f"✅ 预约成功！\n\n"
                    f"📚 课程：{state.get('keyword', '未知')}\n"
                    f"📅 时间：{selected_schedule['date']} {selected_schedule['time']}\n"
                    f"👨‍🏫 老师：{selected_schedule['teacher']}\n"
                    f"🎫 详情：{raw}\n\n"
                    f"请准时参加，如需取消请提前 2 小时告知。"
                )

            except BusinessException as exc:
                self._mark_error(trace, "business_error", exc)
                self.logger.error(
                    f"预约失败: session={session_id}, schedule_id={selected_schedule['id']}, "
                    f"error_type={type(exc).__name__}"
                )
                await self.session.clear_state(session_id)
                return self._handle_business_error(exc)
            except Exception as exc:
                self._mark_error(trace, "system_error", exc)
                self.logger.error(
                    f"预约失败: session={session_id}, schedule_id={selected_schedule['id']}, "
                    f"error_type={type(exc).__name__}"
                )
                await self.session.clear_state(session_id)
                return self._handle_business_error(exc)

        elif state["action"] == "confirming_cancel":
            if user_input in ["是", "yes", "y", "确认", "确定"]:
                booking_id = state.get("booking_id")
                if not booking_id:
                    await self.session.clear_state(session_id)
                    return "❌ 状态异常，预约 ID 丢失，请重新开始"

                try:
                    raw = await self._call_tool(
                        trace,
                        "tool_cancel_booking",
                        "cancel_booking",
                        cancel_booking(
                            booking_id=booking_id,
                            user_id=self.user_id,
                        ),
                    )

                    await self.session.clear_state(session_id)

                    self.logger.info(
                        f"取消预约成功: session={session_id}, booking_id={booking_id}, "
                        f"user_id={self.user_id}"
                    )

                    return f"✅ 已成功取消预约！\n\n🎫 预约 ID：{booking_id}\n📋 处理结果：{raw}"

                except BusinessException as exc:
                    self._mark_error(trace, "business_error", exc)
                    self.logger.error(
                        f"取消预约失败: session={session_id}, booking_id={booking_id}, "
                        f"error_type={type(exc).__name__}"
                    )
                    await self.session.clear_state(session_id)
                    return self._handle_business_error(exc)
                except Exception as exc:
                    self._mark_error(trace, "system_error", exc)
                    self.logger.error(
                        f"取消预约失败: session={session_id}, booking_id={booking_id}, "
                        f"error_type={type(exc).__name__}"
                    )
                    await self.session.clear_state(session_id)
                    return self._handle_business_error(exc)

            elif user_input in ["否", "no", "n", "取消", "不取消了"]:
                self.logger.info(f"用户取消操作: session={session_id}, action=confirming_cancel")
                await self.session.clear_state(session_id)
                return "好的，已取消操作。您的预约保持不变。"

            else:
                return (
                    f"❌ 无法识别您的回复「{user_input}」\n\n"
                    f'请回复 "是" 确认取消，或 "否" 保留预约。'
                )

        else:
            await self.session.clear_state(session_id)
            return "❌ 状态异常，请重新开始"

    # ============================================================
    # 业务错误处理（企业级错误码体系）
    # ============================================================

    def _handle_business_error(self, error: Exception) -> str:
        """
        将业务异常转换为用户友好的提示

        设计模式：策略模式（错误关键词→处理函数映射）
        关键约束（F5.3）：友好提示不得包含原始异常字符串作为子串，防止泄露内部细节。
        """
        error_msg = str(error)

        # 按中文关键词匹配 Service 层抛出的 BusinessException 消息
        # 约束：友好提示不得包含原始异常字符串作为子串
        keyword_map = [
            ("约满", "❌ 该时段已约满 😢\n\n您可以：\n• 回复「重新查询」查看其他时段\n• 或告诉我其他时间偏好"),
            ("已预约", "❌ 您已预约过此课程\n\n回复「我的预约」可查看已预约的课程"),
            ("余额不足", "❌ 课时余额不足\n\n请联系前台充值后再预约\n或回复「余额」查看当前课时"),
            ("扣次失败", "❌ 余额不足导致扣次失败\n\n请联系前台确认卡状态"),
            ("未找到", "❌ 未找到对应记录\n\n可能已被取消，请回复「我的预约」确认"),
            ("找不到", "❌ 未找到对应记录\n\n可能已被取消，请回复「我的预约」确认"),
            ("取消截止", "❌ 无法取消，已超过截止时间\n\n如需帮助，请联系前台处理"),
            ("不可取消", "❌ 无法取消，已超过截止时间\n\n如需帮助，请联系前台处理"),
            ("已开始", "❌ 课程已开始，无法操作\n\n您可以：\n• 回复「查排期」查看其他时段"),
            ("两周", "❌ 超出两周可预约范围\n\n您可以：\n• 回复「查排期」查看可预约的时段"),
            ("已取消", "❌ 该记录已是取消状态\n\n回复「我的预约」查看当前列表"),
            ("状态", "❌ 当前记录状态无法执行此操作\n\n请回复「我的预约」确认状态"),
            ("学员身份", "❌ 当前账号没有学员身份\n\n请使用学员账号登录后再试"),
            ("无效", "❌ 输入参数无效，请重新选择"),
        ]

        for keyword, friendly_msg in keyword_map:
            if keyword in error_msg:
                return friendly_msg

        # 兜底：不回显原始异常（防止泄露 SQL/堆栈/内部细节）
        return "⚠️ 操作失败，请稍后重试或联系客服"

    # ============================================================
    # 分布式锁（防止并发导致重复预约）
    # ============================================================

    async def _acquire_lock(self, lock_key: str, ttl: int = 5) -> bool:
        """
        获取分布式锁

        使用 Redis SET NX EX 命令：
        - NX = 只在 key 不存在时设置（互斥）
        - EX = 自动过期时间（防死锁）

        面试要点：
          为什么用 SET NX EX 而不是单独的 SETNX + EXPIRE？
          因为这两个操作不是原子的，如果 SETNX 成功但 EXPIRE 失败，
          锁就永远不会过期（死锁）。SET NX EX 是原子操作。
        """
        if not self.session.redis:
            return True

        try:
            return await self.session.redis.set(lock_key, "1", nx=True, ex=ttl)
        except Exception:
            return True

    async def _release_lock(self, lock_key: str):
        """
        安全释放分布式锁（Lua 脚本保证原子性）

        面试要点：
          为什么不能用简单的 DEL？
          因为如果锁已过期，别的线程可能已经获取了新锁。
          此时 DEL 会误删别人的锁。

          Lua 脚本保证 GET + DEL 是原子操作：
          只有当锁的值还是自己设置的"1"时才删除。
        """
        if not self.session.redis:
            return

        try:
            lua_script = """
            if redis.call('get', KEYS[1]) == ARGV[1] then
                return redis.call('del', KEYS[1])
            else
                return 0
            end
            """
            await self.session.redis.eval(lua_script, 1, lock_key, "1")
        except Exception:
            pass

    # ============================================================
    # 回复格式化（将 Tool 输出转为自然语言）
    # ============================================================

    def _handle_unknown(self, user_input: str) -> str:
        return (
            f"抱歉，我不太理解「{user_input}」的意思。\n"
            "您可以试试：\n"
            "• 查课程 — 搜索课程列表\n"
            "• 查排期 — 查看未来排期\n"
            "• 我的预约 — 查看预约记录\n"
            "• 余额 — 查看课时余额\n"
            "• 预约 — 预约课程\n"
            "• 取消 — 取消预约"
        )

    def _format_courses(self, raw: str) -> str:
        return f"📚 课程查询结果：\n{raw}"

    def _format_schedules(self, raw: str) -> str:
        return f"📅 排期查询结果：\n{raw}"

    def _format_bookings(self, raw: str) -> str:
        return f"📋 预约记录：\n{raw}"

    def _format_balance(self, raw: str) -> str:
        return f"💰 课时余额：\n{raw}"

    def _format_booking_result(self, raw: str) -> str:
        return f"✅ {raw}"

    def _format_cancel_result(self, raw: str) -> str:
        return f"🗑️ {raw}"

    def _parse_schedules(self, raw: str) -> list[dict]:
        """
        从 Tool 返回的原始文本中解析出结构化排期列表

        输入示例：
            "📅 排期查询结果：\n共 3 个排期：\n- ID:5 | 2026-08-14 | 14:00-15:00 | 王老师 | 剩余:3"

        输出示例：
            [{"id": 5, "date": "2026-08-14", "time": "14:00-15:00", "teacher": "王老师", "remaining": 3}]
        """
        import re

        schedules = []

        for line in raw.split("\n"):
            line = line.strip()

            if not line.startswith("- ID:"):
                continue

            match = re.search(
                r"ID:(\d+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([\d:-]+)\s*\|\s*(.+?)\s*\|\s*剩余:(\d+)",
                line,
            )

            if match:
                schedules.append(
                    {
                        "id": int(match.group(1)),
                        "date": match.group(2),
                        "time": match.group(3),
                        "teacher": match.group(4).strip(),
                        "remaining": int(match.group(5)),
                    }
                )

        return schedules

    def _format_schedule_options(self, schedules: list[dict]) -> str:
        """将排期列表格式化为选项展示给用户"""
        lines = ["📅 找到以下排期，请回复数字选择：\n"]

        for i, s in enumerate(schedules, 1):
            lines.append(
                f"  [{i}] {s['date']} {s['time']} {s['teacher']}（剩余{s['remaining']}个）"
            )

        lines.append('\n例如回复 "1" 或 "第1个"')

        return "\n".join(lines)

    def _parse_user_selection(self, user_input: str, max_index: int) -> int | None:
        """
        解理用户的选择，返回 1-based index 或 None

        支持格式：
          - 数字："1"、"2"、"3"
          - 中文："第1个"、"第一个"、"选二"
        """
        import re

        chinese_map = {
            "一": 1,
            "二": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10,
        }

        match = re.search(r"(\d+)|[选拿选]?(?:第)?([一二三四五六七八九十]+)[个号号]?", user_input)

        if not match:
            return None

        num_str = match.group(1) or match.group(2)

        if num_str.isdigit():
            num = int(num_str)
        else:
            num = chinese_map.get(num_str, 0)

        if 1 <= num <= max_index:
            return num

        return None
