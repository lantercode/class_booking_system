"""
Teacher Service - 教师业务逻辑层

处理教师管理的核心业务逻辑，包括：
- 获取教师信息
- 更新教师信息
"""

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.modules.teacher.models import TeacherProfile, TeacherStatus
from app.modules.user.models import User

logger = logging.getLogger(__name__)


class TeacherService:
    """教师管理服务"""

    async def get_teachers_by_tenant(
        self,
        db: AsyncSession,
        tenant_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """获取租户下所有活跃教师"""
        query = (
            select(User, TeacherProfile)
            .join(TeacherProfile, User.id == TeacherProfile.user_id)
            .where(TeacherProfile.status == TeacherStatus.ACTIVE.value)
        )
        if tenant_id:
            query = query.where(User.tenant_id == tenant_id)

        result = await db.execute(query)
        rows = result.all()

        teachers = []
        for row in rows:
            user, profile = row
            teachers.append({
                "id": user.id,
                "nickname": user.nickname,
                "avatar_url": user.avatar_url,
                "title": profile.title,
                "bio": profile.bio,
                "specialties": profile.specialties,
                "years_of_experience": profile.years_of_experience,
            })
        return teachers

    async def get_teacher_by_user_id(
        self,
        db: AsyncSession,
        user_id: int,
    ) -> dict[str, Any]:
        """根据用户ID获取教师信息"""
        result = await db.execute(
            select(User, TeacherProfile)
            .outerjoin(TeacherProfile, User.id == TeacherProfile.user_id)
            .where(User.id == user_id)
        )
        row = result.first()

        if not row:
            raise NotFoundException("教师信息不存在")

        user, profile = row

        return {
            "user_id": user.id,
            "nickname": user.nickname,
            "phone": user.phone,
            "avatar": user.avatar_url,
            "title": profile.title if profile else None,
            "intro": profile.bio if profile else None,
            "specialties": profile.specialties if profile else None,
            "years_of_experience": profile.years_of_experience if profile else None,
        }

    async def update_teacher_by_user_id(
        self,
        db: AsyncSession,
        user_id: int,
        data: dict[str, Any],
        tenant_id: int | None = None,
    ) -> dict[str, Any]:
        """根据用户ID更新教师信息"""
        # 更新用户表的字段
        user_result = await db.execute(select(User).where(User.id == user_id))
        user = user_result.scalar_one_or_none()

        if not user:
            raise NotFoundException("用户不存在")

        # 更新用户表字段
        if "nickname" in data:
            user.nickname = data["nickname"]

        # 更新教师档案表
        profile_result = await db.execute(
            select(TeacherProfile).where(TeacherProfile.user_id == user_id)
        )
        profile = profile_result.scalar_one_or_none()

        if not profile:
            # 创建教师档案
            from datetime import datetime, timezone
            import random
            date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            random_digits = "".join([str(random.randint(0, 9)) for _ in range(6)])
            teacher_code = f"T{date_str}{random_digits}"
            profile = TeacherProfile(user_id=user_id, tenant_id=tenant_id, teacher_code=teacher_code)
            db.add(profile)

        # 更新教师档案字段
        if "intro" in data:
            profile.bio = data["intro"]
        if "title" in data:
            profile.title = data["title"]
        if "specialties" in data:
            profile.specialties = data["specialties"]
        if "years_of_experience" in data:
            profile.years_of_experience = data["years_of_experience"]

        await db.commit()
        await db.refresh(user)
        await db.refresh(profile)

        return {
            "user_id": user.id,
            "nickname": user.nickname,
            "phone": user.phone,
            "avatar": user.avatar_url,
            "title": profile.title,
            "intro": profile.bio,
            "specialties": profile.specialties,
            "years_of_experience": profile.years_of_experience,
        }