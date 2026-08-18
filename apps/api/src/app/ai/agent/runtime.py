"""
Agent 运行时核心
职责：对话循环、意图→Tool 调度、结果格式化

流程：
  用户输入 → IntentRecognizer → _execute_intent → Tool 函数 → 格式化回复
                                    ↑
                              SessionManager（上下文）
"""

import logging
from typing import Optional

from app.ai.agent.intent import IntentRecognizer
from app.ai.agent.session import SessionManager
from app.ai.mcp_server import (
    query_courses,
    query_schedules,
    get_my_bookings,
    get_my_balance,
    create_booking,
    cancel_booking,
)


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

    def __init__(self, redis_client=None, user_id: int = None):
        self.intent = IntentRecognizer()
        self.session = SessionManager(redis_client)
        self.user_id = user_id
        self.logger = logging.getLogger(__name__)

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
        lock_key = f"ai:lock:{session_id}"
        lock_acquired = False

        try:
            lock_acquired = await self._acquire_lock(lock_key)

            if not lock_acquired:
                self.logger.warning(f"并发拦截: session={session_id}, 获取锁失败")
                return "⏳ 正在处理您的上一个请求，请稍候..."

            state = await self.session.get_state(session_id)
            if state:
                self.logger.info(
                    f"状态恢复: session={session_id}, action={state.get('action')}, "
                    f"user_input={user_input[:20]}"
                )
                return await self._handle_pending_state(user_input, session_id, state)

            user_input = user_input.strip()
            if not user_input:
                return "您好，请问有什么可以帮您？"

            await self.session.add_message(session_id, "user", user_input)

            result = self.intent.recognize(user_input)
            intent_name = result["intent"]
            params = result["params"]

            self.logger.info(
                f"意图识别: session={session_id}, intent={intent_name}, "
                f"params={params}"
            )

            if intent_name == "unknown":
                response = self._handle_unknown(user_input)
                self.logger.warning(f"未知意图: session={session_id}, input={user_input}")
            else:
                response = await self._execute_intent(intent_name, params, session_id)
                self.logger.info(f"Tool调用成功: session={session_id}, intent={intent_name}")

            await self.session.add_message(session_id, "assistant", response)

            return response

        finally:
            if lock_acquired:
                await self._release_lock(lock_key)

    async def _execute_intent(self, intent_name: str, params: dict, session_id: str = "default") -> str:
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
                raw = await query_courses(
                    keyword=params.get("keyword", ""),
                )
                return self._format_courses(raw)

            elif intent_name == "query_schedules":
                raw = await query_schedules(
                    date=params.get("date"),
                    keyword=params.get("keyword", ""),
                )
                return self._format_schedules(raw)

            elif intent_name == "get_my_bookings":
                raw = await get_my_bookings(
                    user_id=self.user_id,
                    status=params.get("status"),
                )
                return self._format_bookings(raw)

            elif intent_name == "get_my_balance":
                raw = await get_my_balance(user_id=self.user_id)
                return self._format_balance(raw)

            elif intent_name == "create_booking":
                if not self.user_id:
                    return "请先登录后再预约课程"

                if "schedule_id" not in params:
                    raw = await query_schedules(
                        date=params.get("date"),
                        keyword=params.get("keyword", ""),
                    )

                    schedules = self._parse_schedules(raw)

                    if not schedules:
                        return f"📅 没有找到符合条件的排期\n{raw}"

                    await self.session.set_state(session_id, {
                        "action": "selecting_schedule",
                        "schedules": schedules,
                        "keyword": params.get("keyword", ""),
                        "date": params.get("date"),
                    })

                    return self._format_schedule_options(schedules)

                raw = await create_booking(
                    schedule_id=params["schedule_id"],
                    user_id=self.user_id,
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
                    f"存入取消确认状态: session={session_id}, "
                    f"booking_id={params['booking_id']}"
                )

                verify_state = await self.session.get_state(session_id)
                self.logger.info(f"验证状态存储: session={session_id}, state={verify_state}")

                return (
                    f"⚠️ 您确定要取消预约 #{params['booking_id']} 吗？\n\n"
                    f"请回复：\n"
                    f"• \"是\" 或 \"确认\" → 执行取消\n"
                    f"• \"否\" 或 \"取消\" → 保留预约"
                )

            else:
                return self._handle_unknown(intent_name)

        except Exception as e:
            return self._handle_business_error(e)

    async def _handle_pending_state(self, user_input: str, session_id: str, state: dict):
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
            f"input={user_input}"
        )

        if state["action"] == "selecting_schedule":
            schedules = state.get("schedules", [])

            selection = self._parse_user_selection(user_input, len(schedules))

            if selection is None:
                return (
                    f"❌ 无法识别您的选择「{user_input}」\n\n"
                    f"请回复数字，如 \"1\"、\"2\" 或 \"第1个\"\n\n"
                    f"{self._format_schedule_options(schedules)}"
                )

            selected_schedule = schedules[selection - 1]

            self.logger.info(
                f"用户选择排期: session={session_id}, selection={selection}, "
                f"schedule_id={selected_schedule['id']}"
            )

            try:
                raw = await create_booking(
                    user_id=self.user_id,
                    schedule_id=selected_schedule["id"],
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

            except Exception as e:
                self.logger.error(
                    f"预约失败: session={session_id}, schedule_id={selected_schedule['id']}, "
                    f"error={str(e)}"
                )
                await self.session.clear_state(session_id)
                return self._handle_business_error(e)

        elif state["action"] == "confirming_cancel":
            if user_input in ["是", "yes", "y", "确认", "确定"]:
                booking_id = state.get("booking_id")
                if not booking_id:
                    await self.session.clear_state(session_id)
                    return "❌ 状态异常，预约 ID 丢失，请重新开始"

                try:
                    raw = await cancel_booking(
                        booking_id=booking_id,
                        user_id=self.user_id,
                    )

                    await self.session.clear_state(session_id)

                    self.logger.info(
                        f"取消预约成功: session={session_id}, booking_id={booking_id}, "
                        f"user_id={self.user_id}"
                    )

                    return (
                        f"✅ 已成功取消预约！\n\n"
                        f"🎫 预约 ID：{booking_id}\n"
                        f"📋 处理结果：{raw}"
                    )

                except Exception as e:
                    self.logger.error(
                        f"取消预约失败: session={session_id}, booking_id={booking_id}, "
                        f"error={str(e)}"
                    )
                    await self.session.clear_state(session_id)
                    return self._handle_business_error(e)

            elif user_input in ["否", "no", "n", "取消", "不取消了"]:
                self.logger.info(f"用户取消操作: session={session_id}, action=confirming_cancel")
                await self.session.clear_state(session_id)
                return "好的，已取消操作。您的预约保持不变。"

            else:
                return (
                    f"❌ 无法识别您的回复「{user_input}」\n\n"
                    f"请回复 \"是\" 确认取消，或 \"否\" 保留预约。"
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

        面试要点：
          为什么不直接返回 str(error)？
          1. 异常信息可能包含技术细节（SQL、堆栈），不适合展示给用户
          2. 不同异常需要不同的引导动作（余额不足→去充值，名额已满→查其他时段）
          3. 错误码便于日志分析和监控告警

        设计模式：策略模式（错误码→处理函数映射）
        """
        error_msg = str(error).upper()

        error_map = {
            "SCHEDULE_FULL": (
                "❌ 该时段刚被约满 😢\n\n"
                "您可以：\n"
                "• 回复「重新查询」查看其他时段\n"
                "• 或告诉我其他时间偏好"
            ),
            "ALREADY_BOOKED": (
                "❌ 您已预约过此课程\n\n"
                "回复「我的预约」可查看已预约的课程"
            ),
            "BALANCE_INSUFFICIENT": (
                "❌ 课时余额不足\n\n"
                "请联系前台充值后再预约\n"
                "或回复「余额」查看当前课时"
            ),
            "BOOKING_NOT_FOUND": (
                "❌ 未找到该预约记录\n\n"
                "可能已被取消，请回复「我的预约」确认"
            ),
            "CANCEL_DEADLINE_PASSED": (
                "❌ 已超过取消截止时间（需提前2小时）\n\n"
                "如需帮助，请联系前台处理"
            ),
            "SCHEDULE_EXPIRED": (
                "❌ 该课程已开始，无法预约\n\n"
                "您可以：\n"
                "• 回复「查排期」查看其他时段"
            ),
            "SCHEDULE_TOO_FAR": (
                "❌ 只能预约未来两周内的课程\n\n"
                "您可以：\n"
                "• 回复「查排期」查看可预约的时段"
            ),
        }

        for code, friendly_msg in error_map.items():
            if code in error_msg:
                return friendly_msg

        return f"⚠️ 处理请求时出错：{error}\n请稍后重试或联系客服"

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
        
        for line in raw.split('\n'):
            line = line.strip()
            
            if not line.startswith('- ID:'):
                continue
            
            match = re.search(
                r'ID:(\d+)\s*\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*([\d:-]+)\s*\|\s*(.+?)\s*\|\s*剩余:(\d+)',
                line
            )
            
            if match:
                schedules.append({
                    "id": int(match.group(1)),
                    "date": match.group(2),
                    "time": match.group(3),
                    "teacher": match.group(4).strip(),
                    "remaining": int(match.group(5)),
                })
        
        return schedules

    def _format_schedule_options(self, schedules: list[dict]) -> str:
        """将排期列表格式化为选项展示给用户"""
        lines = ["📅 找到以下排期，请回复数字选择：\n"]
        
        for i, s in enumerate(schedules, 1):
            lines.append(
                f"  [{i}] {s['date']} {s['time']} {s['teacher']}（剩余{s['remaining']}个）"
            )
        
        lines.append("\n例如回复 \"1\" 或 \"第1个\"")
        
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
            "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
            "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
        }
        
        match = re.search(r'(\d+)|[选拿选]?(?:第)?([一二三四五六七八九十]+)[个号号]?', user_input)
        
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