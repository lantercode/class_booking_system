"""
工具调用上下文
职责：封装用户身份（user_id, tenant_id, role），自动从 JWT 注入
"""

from dataclasses import dataclass


@dataclass
class ToolContext:
    """Tool 调用上下文，每个 Tool 都会收到这个对象"""
    user_id: int          # 用户 ID
    tenant_id: int        # 租户 ID（多租户隔离）
    role: str             # 角色：student / teacher / admin

    def is_student(self) -> bool:
        return self.role == "student"

    def is_teacher(self) -> bool:
        return self.role == "teacher"

    def is_admin(self) -> bool:
        return self.role == "admin"