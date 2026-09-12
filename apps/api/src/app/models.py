"""
所有 SQLAlchemy 模型的统一导入入口

Alembic 需要导入此文件以检测所有模型。
新增模型时，只需在此处添加导入即可。
"""

# 核心模型
from app.modules.tenant.models import Tenant
from app.modules.user.models import User

# 角色权限模型（在 auth 模块中）
from app.modules.auth.models import Role, Permission, UserRole, RolePermission, WechatAccount

# 业务模型
from app.modules.course.models import Course, Classroom
from app.modules.schedule.models import CourseSchedule
from app.modules.booking.models import Booking
from app.modules.order.models import Order
from app.modules.payment.models import Payment
from app.modules.teacher.models import TeacherProfile
from app.modules.student.models import StudentProfile

# 会员卡模块（新增）
from app.modules.membership.models import (
    MembershipCardProduct,
    MembershipCard,
    MembershipCardTransaction,
    MembershipCardFreeze,
)

# 审计日志
from app.modules.notification.models import AuditLog

__all__ = [
    # 核心
    "Tenant",
    "User",
    # 角色权限
    "Role",
    "Permission",
    "UserRole",
    "RolePermission",
    # 业务
    "Course",
    "CourseSchedule",
    "Classroom",
    "Booking",
    "Order",
    "Payment",
    "TeacherProfile",
    "StudentProfile",
    # 会员卡
    "MembershipCardProduct",
    "MembershipCard",
    "MembershipCardTransaction",
    "MembershipCardFreeze",
    # 其他
    "AuditLog",
    "WechatAccount",
]