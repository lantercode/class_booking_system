"""
管理后台模块 - 业务逻辑层

用户管理真实实现（F2.1）：
- 所有用户写操作复用 user 模块的 UserService（跨模块复用 Service，合规分层）
- admin 契约（username/is_active）在Service内映射为 user 契约（nickname/status）
- 批量删除在同一 AsyncSession 中统一提交（原子语义）
- public/stats 为按当前租户的真实聚合查询

注意：get_my_permissions 原本已是真实实现（RBAC checker），保持不变。
"""

import logging

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationException
from app.core.rbac.cache import clear_user_permission_cache
from app.core.tenant_context import get_tenant_id
from app.modules.user.schemas import UserCreate, UserResponse, UserUpdate
from app.modules.user.service import UserService

logger = logging.getLogger(__name__)


class AdminUserService:
    """用户管理服务（真实实现，包装 UserService）"""

    def __init__(self):
        self.user_service = UserService()

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _to_admin_dict(user: UserResponse) -> dict:
        """
        UserResponse → admin 响应 dict

        保留 Mock 时期响应中的 username / is_active 字段作为兼容别名：
        - username  ← nickname（无昵称时回退 phone）
        - is_active ← status == 1
        真实字段（status / nickname / public_id 等）同时完整返回。
        """
        data = user.model_dump()
        data["username"] = user.nickname or user.phone
        data["is_active"] = user.status == 1
        return data

    # ------------------------------------------------------------------
    # 用户 CRUD
    # ------------------------------------------------------------------

    async def create_user(
        self,
        db: AsyncSession,
        data: dict,
        current_user: dict,
    ) -> dict:
        """
        创建新用户（真实落库）

        业务规则（由 UserService 保证）：
        1. 只有拥有 user:create 权限的用户才能调用（由装饰器保证）
        2. 手机号 / 邮箱在本租户内唯一
        3. 创建用户并按 role_ids 分配角色（teacher/student 自动建 Profile）
        4. tenant_id 由 TenantAwareRepository 从 ContextVar 注入

        Raises:
            ValidationException: 手机号/邮箱已存在
        """
        logger.info(
            f"[Admin] 用户 {current_user['user_id']} 正在创建用户: phone={data.get('phone')}"
        )

        # admin 契约 → user 契约映射：username → nickname
        payload = UserCreate(
            phone=data["phone"],
            password=data["password"],
            email=data.get("email"),
            nickname=data.get("username"),
            role_ids=data.get("role_ids") or [],
        )

        result = await self.user_service.create_user(
            db, payload, operator_id=current_user["user_id"]
        )

        logger.info(f"[Admin] ✅ 用户创建成功: id={result.id}")
        return self._to_admin_dict(result)

    async def update_user(
        self,
        db: AsyncSession,
        user_id: int,
        data: dict,
        current_user: dict,
        redis_client=None,
    ) -> dict:
        """
        更新用户信息（真实落库）

        权限要求：user:update + user:read（AND 逻辑，装饰器保证）

        角色变更（传 role_ids）时由 UserService 内部调用 assign_roles
        并清除目标用户权限缓存，admin 层不重复清理。
        """
        logger.info(f"[Admin] 用户 {current_user['user_id']} 正在更新用户 {user_id}")

        # admin 契约 → user 契约映射：username → nickname，is_active → status
        payload = UserUpdate(
            phone=data.get("phone"),
            email=data.get("email"),
            nickname=data.get("username"),
            status=(1 if data["is_active"] else 0)
            if data.get("is_active") is not None
            else None,
            role_ids=data.get("role_ids"),
        )

        result = await self.user_service.update_user(
            db,
            user_id,
            payload,
            operator_id=current_user["user_id"],
            redis_client=redis_client,
        )

        logger.info(f"[Admin] ✅ 用户 {user_id} 更新成功")
        return self._to_admin_dict(result)

    async def delete_user(
        self,
        db: AsyncSession,
        user_id: int,
        current_user: dict,
        redis_client=None,
    ) -> dict:
        """
        删除用户（软删除，真实生效）

        权限要求：user:delete（专门的高危权限）

        安全措施：
        1. 需要专门的删除权限（装饰器保证）
        2. 不能删除自己（此处预检 + UserService 二次校验，纵深防御）
        3. 教师有未来未完成排课时拒绝删除（UserService 保证）
        4. 删除后由 UserService 清除权限缓存
        """
        operator_id = current_user["user_id"]

        if user_id == operator_id:
            raise ValidationException("不能删除自己的账号")

        logger.warning(f"[Admin] ⚠️ 危险操作：用户 {operator_id} 正在删除用户 {user_id}")

        await self.user_service.delete_user(
            db,
            user_id,
            operator_id=operator_id,
            redis_client=redis_client,
        )

        logger.warning(f"[Admin] ✅ 用户 {user_id} 已被删除，操作人: {operator_id}")
        return {"message": f"用户 {user_id} 已删除"}

    async def list_users(
        self,
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
    ) -> dict:
        """
        获取用户列表（真实分页，自动租户隔离 + 软删除过滤）

        权限要求：user:read
        """
        logger.debug(f"[Admin] 获取用户列表: page={page}, size={page_size}")

        result = await self.user_service.list_users(
            db,
            keyword=keyword,
            page=page,
            page_size=page_size,
        )

        return {
            "total": result.total,
            "page": result.page,
            "page_size": result.page_size,
            "items": [self._to_admin_dict(u) for u in result.items],
        }

    async def get_user(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> dict:
        """
        获取用户详情（真实查询）

        权限要求：user:read

        Raises:
            NotFoundException: 用户不存在 / 已删除 / 跨租户
        """
        result = await self.user_service.get_user_by_id(db, user_id)
        return self._to_admin_dict(result)

    # ------------------------------------------------------------------
    # 角色分配与批量删除
    # ------------------------------------------------------------------

    async def assign_roles(
        self,
        db: AsyncSession,
        user_id: int,
        role_ids: list[int],
        current_user: dict,
        redis_client=None,
    ) -> dict:
        """
        为用户分配角色（覆盖式，真实生效）

        双重验证（router 层）：admin/manager 角色 + role:assign 权限。
        UserService 内部再次校验操作人须为 admin/super_admin，并处理
        TeacherProfile / StudentProfile 联动与权限缓存清除。
        """
        logger.info(
            f"[Admin] 用户 {current_user['user_id']} 正在为用户 {user_id} 分配角色: {role_ids}"
        )

        await self.user_service.assign_roles(
            db,
            user_id,
            role_ids,
            operator_id=current_user["user_id"],
            redis_client=redis_client,
        )

        return {"user_id": user_id, "role_ids": role_ids}

    async def batch_delete_users(
        self,
        db: AsyncSession,
        user_ids: list[int],
        current_user: dict,
        redis_client=None,
    ) -> dict:
        """
        批量删除用户（软删除，原子语义）

        事务：所有删除在同一 AsyncSession 中执行（auto_commit=False），
        由本方法统一 commit；任一用户校验失败（不存在 / 删自己 /
        教师有未来排课）整体回滚，由 get_session 异常分支兜底。

        权限缓存：统一提交成功后逐个清除。
        """
        operator_id = current_user["user_id"]

        if operator_id in user_ids:
            raise ValidationException("不能删除自己的账号")

        logger.critical(
            f"[Admin] 极危操作：用户 {operator_id} "
            f"(roles={current_user.get('role_codes')}) "
            f"正在批量删除用户: {user_ids}"
        )

        for uid in user_ids:
            await self.user_service.delete_user(
                db,
                uid,
                operator_id=operator_id,
                auto_commit=False,
            )

        await db.commit()

        if redis_client:
            tenant_id = current_user.get("tenant_id")
            for uid in user_ids:
                await clear_user_permission_cache(redis_client, tenant_id, uid)

        logger.warning(f"[Admin] ✅ 批量删除完成: {len(user_ids)} 个用户，操作人: {operator_id}")
        return {"deleted_count": len(user_ids), "user_ids": user_ids}

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    async def get_public_stats(self, db: AsyncSession) -> dict:
        """
        公开统计数据（真实聚合）

        范围决策：按当前租户聚合。/admin/public/stats 不在租户中间件
        跳过白名单中，HTTP 请求必须携带租户头，ContextVar 必有 tenant_id；
        "学校简介中的数字"语义上即单个学校的数据。
        ContextVar 缺失（理论上 HTTP 路径不可达）时降级为全平台聚合。

        注意：select(func.count()) 的 column_descriptions entity 为 None，
        不会触发 ORM 租户自动注入（见 tenant_query.py），因此显式过滤租户。
        """
        from app.modules.auth.models import Role, UserRole
        from app.modules.booking.models import Booking
        from app.modules.course.models import Course
        from app.modules.user.models import User

        tenant_id = get_tenant_id()
        if not tenant_id:
            logger.warning("[Admin] public/stats 无租户上下文，降级为全平台聚合")

        def _role_user_count(role_code: str):
            query = (
                select(func.count(func.distinct(User.id)))
                .select_from(User)
                .join(UserRole, User.id == UserRole.user_id)
                .join(
                    Role,
                    UserRole.role_id == Role.id,
                )
                .where(Role.code == role_code, User.deleted_at.is_(None))
            )
            if tenant_id:
                query = query.where(
                    User.tenant_id == tenant_id,
                    or_(Role.tenant_id == tenant_id, Role.tenant_id.is_(None)),
                )
            return query

        students_result = await db.execute(_role_user_count("student"))
        total_students = students_result.scalar() or 0

        teachers_result = await db.execute(_role_user_count("teacher"))
        total_teachers = teachers_result.scalar() or 0

        classes_query = select(func.count()).select_from(Course).where(Course.deleted_at.is_(None))
        if tenant_id:
            classes_query = classes_query.where(Course.tenant_id == tenant_id)
        classes_result = await db.execute(classes_query)
        total_classes = classes_result.scalar() or 0

        # Booking 无 deleted_at 字段，统计全量
        bookings_query = select(func.count()).select_from(Booking)
        if tenant_id:
            bookings_query = bookings_query.where(Booking.tenant_id == tenant_id)
        bookings_result = await db.execute(bookings_query)
        total_bookings = bookings_result.scalar() or 0

        return {
            "total_students": total_students,
            "total_teachers": total_teachers,
            "total_classes": total_classes,
            "total_bookings": total_bookings,
        }

    # ------------------------------------------------------------------
    # 自身权限（原本已是真实实现，保持不变）
    # ------------------------------------------------------------------

    @staticmethod
    async def get_my_permissions(
        db: AsyncSession,
        redis_client,
        current_user: dict,
    ) -> dict:
        """
        获取当前用户的完整权限列表（用于前端渲染菜单/按钮）

        这是一个很好的 RBAC 使用示例：
        - 前端调用此接口获取当前用户的所有权限
        - 根据返回的权限列表控制 UI 元素的显示/隐藏
        - 如：有 'user:create' 权限才显示"新建用户"按钮
        """
        from app.core.rbac.checker import get_user_permissions

        user_id = current_user["user_id"]
        tenant_id = current_user["tenant_id"]

        logger.info(f"[Admin] 获取用户 {user_id} 的权限列表")

        permissions = await get_user_permissions(
            db_session=db,
            redis_client=redis_client,
            user_id=user_id,
            tenant_id=tenant_id,
        )

        return {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "permissions": [
                {"code": p, "name": p.split(":")[1], "module": p.split(":")[0]}
                for p in sorted(permissions)
            ],
            "roles": current_user.get("role_codes", []),
            "cached": len(permissions) > 0,  # 简单判断是否命中缓存
        }


# 创建服务实例
admin_user_service = AdminUserService()
