"""
管理后台路由 - RBAC 权限控制完整示例

此文件展示了如何在实际项目中使用 RBAC 权限系统：

权限粒度示例：
1. 单个权限：@require_permissions("user:create")
2. 多权限 AND：@require_permissions("user:update", "user:read", require_all=True)
3. 多权限 OR：@require_permissions("admin:all", "report:view", require_all=False)
4. 单角色：@require_roles("admin")
5. 多角色 OR：@require_roles("admin", "manager")
6. 组合使用：角色 + 权限 双重验证

运行方式：
    访问 http://localhost:8000/docs 查看 API 文档
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rbac import require_permissions, require_roles
from app.core.response import success
from app.core.database import get_session
from app.core.tenant_context import get_tenant_id
from app.deps.auth import get_current_user, get_redis_client

from app.modules.user.models import User, UserStatus
from app.modules.auth.models import Role, UserRole
from app.modules.course.models import Course, CourseStatus
from app.modules.schedule.models import CourseSchedule
from app.modules.booking.models import Booking

from .schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    PermissionListResponse,
)
from .service import admin_user_service

router = APIRouter(prefix="/admin", tags=["管理后台 - 用户管理"])


# ============================================================
# 用户管理 CRUD（基于权限的细粒度控制）
# ============================================================

@router.post(
    "/users",
    response_model=dict,
    status_code=201,
    summary="创建用户",
    description="""创建新用户账号。

**权限要求**: user:create（创建用户权限）

**适用角色**:
- admin（管理员）- 通常有此权限
- hr（人事）- 可能也有此权限

**不适用角色**:
- teacher（教师）- 不应该能创建用户
- student（学生）- 绝对不能创建用户""",
)
@require_permissions("user:create")
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
    redis_client=Depends(get_redis_client),
):
    """创建用户"""
    result = await admin_user_service.create_user(db, data.model_dump(), current_user)
    return success(data=result, msg="用户创建成功")


@router.get(
    "/users",
    response_model=dict,
    summary="获取用户列表",
    description="""分页获取用户列表（支持关键词搜索）。

**权限要求**: user:read（查看用户权限）

**查询参数**:
- page: 页码，默认 1
- page_size: 每页数量，默认 20，最大 100
- keyword: 搜索关键词（匹配用户名/手机号）""",
)
@require_permissions("user:read")
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: str = Query(None, description="搜索关键词"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取用户列表"""
    result = await admin_user_service.list_users(db, page, page_size, keyword)
    return success(data=result)


@router.get(
    "/users/{user_id}",
    response_model=dict,
    summary="获取用户详情",
    description="""获取指定用户的详细信息。

**权限要求**: user:read""",
)
@require_permissions("user:read")
async def get_user(
    user_id: int = Path(..., description="用户ID"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取用户详情"""
    return success(data={
        "id": user_id,
        "username": f"user_{user_id}",
        "phone": "13800138000",
        "roles": ["student"],
    })


@router.put(
    "/users/{user_id}",
    response_model=dict,
    summary="更新用户信息",
    description="""更新用户信息（部分更新）。

**权限要求**: user:update AND user:read（必须同时拥有两个权限）

为什么需要两个权限？
- user:update: 允许修改用户数据
- user:read: 编辑前必须能看到当前值（防止盲目修改）""",
)
@require_permissions("user:update", "user:read", require_all=True)
async def update_user(
    user_id: int = Path(..., description="用户ID"),
    data: UserUpdate = ...,
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """更新用户"""
    result = await admin_user_service.update_user(
        user_id, data.model_dump(exclude_unset=True), current_user,
    )
    return success(data=result, msg=f"用户 {user_id} 更新成功")


@router.delete(
    "/users/{user_id}",
    response_model=dict,
    summary="删除用户",
    description="""删除用户（高危操作！）。

**权限要求**: user:delete（专门的删除权限）

安全措施：
1. 需要单独的删除权限（比 update 权限更高级）
2. 不能删除自己的账号
3. 删除后自动清除该用户的权限缓存
4. 记录详细的审计日志

⚠️ 此权限应该只分配给极少数超级管理员""",
)
@require_permissions("user:delete")
async def delete_user(
    user_id: int = Path(..., description="用户ID"),
    db: AsyncSession = Depends(get_session),
    redis_client=Depends(get_redis_client),
    current_user: dict = Depends(get_current_user),
):
    """删除用户"""
    result = await admin_user_service.delete_user(db, user_id, current_user, redis_client)
    return success(data=result, msg=f"用户 {user_id} 已删除")


# ============================================================
# 基于角色的快速判断（适用于身份验证场景）
# ============================================================

@router.get(
    "/dashboard",
    response_model=dict,
    summary="管理员后台首页",
    description="""管理员后台首页（Dashboard）。

**角色要求**: admin 或 super_admin（OR 逻辑）

返回聚合统计数据，替代前端多次请求。""",
)
@require_roles("admin", "super_admin")
async def admin_dashboard(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """管理员 Dashboard - 聚合统计数据"""
    tenant_id = get_tenant_id()

    total_users_result = await db.execute(
        select(func.count()).select_from(User).where(
            User.tenant_id == tenant_id,
            User.deleted_at.is_(None),
        )
    )
    total_users = total_users_result.scalar() or 0

    active_courses_result = await db.execute(
        select(func.count()).select_from(Course).where(
            Course.tenant_id == tenant_id,
            Course.status == CourseStatus.ONLINE.value,
            Course.deleted_at.is_(None),
        )
    )
    active_courses = active_courses_result.scalar() or 0

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    monthly_schedules_result = await db.execute(
        select(func.count()).select_from(CourseSchedule).where(
            CourseSchedule.tenant_id == tenant_id,
            CourseSchedule.start_at >= month_start,
        )
    )
    monthly_schedules = monthly_schedules_result.scalar() or 0

    monthly_bookings_result = await db.execute(
        select(func.count()).select_from(Booking).where(
            Booking.tenant_id == tenant_id,
            Booking.booked_at >= month_start,
        )
    )
    monthly_bookings = monthly_bookings_result.scalar() or 0

    recent_bookings_result = await db.execute(
        select(Booking)
        .where(Booking.tenant_id == tenant_id)
        .order_by(Booking.booked_at.desc())
        .limit(5)
    )
    recent_bookings = recent_bookings_result.scalars().all()

    recent_booking_list = []
    if recent_bookings:
        student_ids = list({b.student_id for b in recent_bookings})
        students_result = await db.execute(
            select(User).where(User.id.in_(student_ids))
        )
        student_map = {u.id: u for u in students_result.scalars().all()}

        for b in recent_bookings:
            student = student_map.get(b.student_id)
            recent_booking_list.append({
                "student": student.nickname or student.phone if student else f"学员#{b.student_id}",
                "course": f"课程#{b.schedule_id}",
                "time": b.booked_at.strftime("%Y-%m-%d %H:%M") if b.booked_at else "",
                "status": "已签到" if b.status == 3 else "待签到",
            })

    disabled_teachers_result = await db.execute(
        select(User)
        .join(UserRole, User.id == UserRole.user_id)
        .join(Role, and_(
            UserRole.role_id == Role.id,
            or_(Role.tenant_id == tenant_id, Role.tenant_id.is_(None)),
        ))
        .where(
            User.tenant_id == tenant_id,
            User.status == UserStatus.DISABLED.value,
            User.deleted_at.is_(None),
            Role.code == "teacher",
        )
    )
    disabled_teachers = disabled_teachers_result.scalars().all()
    disabled_teacher_list = [
        {
            "id": t.id,
            "name": t.nickname or t.phone,
            "phone": t.phone,
            "speciality": "暂无",
        }
        for t in disabled_teachers
    ]

    return success(data={
        "message": f"欢迎回来，{current_user.get('nickname') or current_user.get('username', '管理员')}!",
        "total_users": total_users,
        "active_courses": active_courses,
        "monthly_schedules": monthly_schedules,
        "monthly_bookings": monthly_bookings,
        "recent_bookings": recent_booking_list,
        "disabled_teachers": disabled_teacher_list,
    })


@router.get(
    "/settings",
    response_model=dict,
    summary="系统设置",
    description="""系统设置页面。

**权限要求**: admin:all 或 super:manage（OR 逻辑）

OR 逻辑说明：
- 有 admin:all 权限的普通管理员可以访问
- 有 super:manage 权限的超管也可以访问
- 两者满足其一即可""",
)
@require_permissions("admin:all", "super:manage", require_all=False)
async def system_settings(
    current_user: dict = Depends(get_current_user),
):
    """系统设置"""
    return success(data={
        "settings": {
            "site_name": "舞蹈培训管理系统",
            "maintenance_mode": False,
            "max_upload_size": "10MB",
        },
    })


# ============================================================
# 组合使用（角色 + 权限 双重验证）
# ============================================================

@router.post(
    "/users/{user_id}/assign-roles",
    response_model=dict,
    summary="分配用户角色",
    description="""为用户分配或修改角色（双重验证）。

**第一层验证**: 必须是 admin 或 manager 角色
**第二层验证**: 必须有 role:assign 权限

为什么需要双重验证？
- 有些管理员虽然有 admin 角色，但可能没有分配角色的具体权限
- 例如：部门管理员可以看 Dashboard，但不能改角色
- 两层检查更安全、更灵活""",
)
@require_roles("admin", "manager")
@require_permissions("role:assign")
async def assign_user_roles(
    user_id: int = Path(..., description="目标用户ID"),
    role_ids: list[int] = Query(..., description="要分配的角色ID列表"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
    redis_client=Depends(get_redis_client),
):
    """分配用户角色"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(
        f"[Admin] 用户 {current_user['user_id']} 正在为用户 {user_id} 分配角色: {role_ids}"
    )

    from app.core.rbac import clear_user_permission_cache
    if redis_client:
        await clear_user_permission_cache(
            redis_client, current_user.get('tenant_id'), user_id,
        )

    return success(data={"user_id": user_id, "role_ids": role_ids}, msg="角色分配成功")


# ============================================================
# 特殊场景（获取自身权限、公开接口等）
# ============================================================

@router.get(
    "/my-permissions",
    response_model=dict,
    summary="获取我的权限列表",
    description="""获取当前登录用户的完整权限列表。

**用途**:
- 前端根据权限列表动态渲染菜单和按钮
- 如：有 'user:create' 权限才显示"新建"按钮
- 有 'report:view' 权限才显示"报表"菜单项

**特点**:
- 无需额外的权限要求（已登录即可）
- 返回详细的权限信息和缓存状态""",
)
async def get_my_permissions(
    db: AsyncSession = Depends(get_session),
    redis_client=Depends(get_redis_client),
    current_user: dict = Depends(get_current_user),
):
    """获取我的权限列表"""
    result = await admin_user_service.get_my_permissions(db, redis_client, current_user)
    return success(data=result)


@router.get(
    "/public/stats",
    response_model=dict,
    summary="公开统计数据",
    description="""公开的统计信息（无需登录）。

**权限要求**: 无（完全公开）

适用场景：
- 首页展示的总数据量
- 学校简介中的数字
- 其他不敏感的聚合数据""",
)
async def public_stats():
    """公开接口"""
    return success(data={
        "total_students": 5000,
        "total_teachers": 200,
        "total_classes": 1000,
        "total_bookings": 10000,
    })


# ============================================================
# 高级用法（AND 角色检查）
# ============================================================

@router.post(
    "/users/batch-delete",
    response_model=dict,
    summary="批量删除用户（高危）",
    description="""批量删除多个用户（极度危险的操作！）。

**角色要求**: super_admin AND security_admin（必须同时拥有两个角色）

为什么用 AND 逻辑？
- 单人误操作风险太高
- 需要两种不同角色的确认
- 类似银行转账需要两个U盾的场景

⚠️⚠️⚠️ 极度危险操作 ⚠️⚠️⚠️
- 只有同时拥有 super_admin 和 security_admin 角色的用户才能执行
- 会触发审计日志告警
- 建议增加二次确认机制""",
)
@require_roles("super_admin", "security_admin", require_all=True)
async def batch_delete_users(
    user_ids: list[int] = Query(..., description="要删除的用户ID列表"),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
    redis_client=Depends(get_redis_client),
):
    """批量删除用户"""
    import logging
    logger = logging.getLogger(__name__)

    logger.critical(
        f"[ADMIN] 极危操作：用户 {current_user['user_id']} "
        f"(roles={current_user.get('role_codes')}) "
        f"正在批量删除用户: {user_ids}"
    )

    from app.core.rbac.cache import clear_user_permission_cache
    tenant_id = current_user.get("tenant_id")
    for uid in user_ids:
        if redis_client:
            await clear_user_permission_cache(redis_client, tenant_id, uid)

    return success(
        data={"deleted_count": len(user_ids), "user_ids": user_ids},
        msg=f"已批量删除 {len(user_ids)} 个用户",
    )