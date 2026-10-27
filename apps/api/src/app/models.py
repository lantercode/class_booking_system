"""
所有 SQLAlchemy 模型的统一导入入口

Alembic 需要导入此文件以检测所有模型。
新增模型时，只需在此处添加导入即可。
"""

# 核心模型
# 角色权限模型（在 auth 模块中）
from app.modules.auth.models import Permission, Role, RolePermission, UserRole, WechatAccount
from app.modules.user.models import User
from app.modules.tenant.models import Tenant

# 业务模型
from app.modules.booking.models import Booking
from app.modules.course.models import Classroom, Course
from app.modules.notification.models import AuditLog
from app.modules.order.models import Order
from app.modules.payment.models import Payment
from app.modules.schedule.models import CourseSchedule
from app.modules.student.models import StudentProfile
from app.modules.teacher.models import TeacherProfile

# 会员卡模块
from app.modules.membership.models import (
    MembershipCard,
    MembershipCardFreeze,
    MembershipCardProduct,
    MembershipCardTransaction,
)

# 文件上传（依赖 users 表先注册）
from app.modules.upload.models import FileObject

# 首页配置（FK operator_id → users.id，依赖 User 先注册）
from app.modules.home_config.models import HomeConfig

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
    "FileObject",
    # 首页配置
    "HomeConfig",
]
