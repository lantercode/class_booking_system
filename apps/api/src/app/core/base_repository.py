"""
BaseRepository - 通用数据访问层（Repository Pattern）

提供统一的 CRUD 操作，减少重复代码，提升开发效率。
支持：
- 泛型设计（适用于所有 SQLAlchemy Model）
- 完整 CRUD（Create/Read/Update/Delete）
- 分页查询（带总数统计）
- 批量操作（bulk_create/bulk_update）
- 软删除（Soft Delete）
- 多租户自动过滤（TenantAwareRepository）
"""

import logging
from typing import TypeVar, Generic, Type, Optional, List, Dict, Any, Union, Tuple
from datetime import datetime
from sqlalchemy import select, update, delete, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

logger = logging.getLogger(__name__)

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """
    通用 Repository 基类
    
    Usage:
        class UserRepository(BaseRepository[User]):
            model_class = User
            
        repo = UserRepository()
        user = await repo.get_by_id(db, user_id=1)
    """

    model_class: Type[ModelType] = None

    def __init__(self):
        if self.model_class is None:
            raise NotImplementedError(
                f"{self.__class__.__name__} 必须指定 model_class 属性！\n"
                f"示例: class {self.__class__.__name__}(BaseRepository[User]):\n"
                f"    model_class = User"
            )

    def _has_soft_delete(self) -> bool:
        """检查模型是否支持软删除（是否有 deleted_at 字段）"""
        return hasattr(self.model_class, 'deleted_at')

    async def get_by_id(
        self,
        db: AsyncSession,
        id: int,
        *,
        include_deleted: bool = False,
    ) -> Optional[ModelType]:
        """根据 ID 查询单条记录"""
        query = select(self.model_class).where(self.model_class.id == id)
        
        if not include_deleted and self._has_soft_delete():
            query = query.where(self.model_class.deleted_at.is_(None))
        
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_one(
        self,
        db: AsyncSession,
        *,
        filters: Optional[Dict[str, Any]] = None,
        include_deleted: bool = False,
    ) -> Optional[ModelType]:
        """根据条件查询单条记录"""
        query = select(self.model_class)
        
        if filters:
            conditions = [
                getattr(self.model_class, key) == value
                for key, value in filters.items()
            ]
            query = query.where(and_(*conditions))
        
        if not include_deleted and self._has_soft_delete():
            query = query.where(self.model_class.deleted_at.is_(None))
        
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        db: AsyncSession,
        *,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        order_desc: bool = True,
        include_deleted: bool = False,
    ) -> List[ModelType]:
        """查询所有符合条件的记录（不分页）"""
        query = select(self.model_class)
        
        if filters:
            conditions = [
                getattr(self.model_class, key) == value
                for key, value in filters.items()
            ]
            query = query.where(and_(*conditions))
        
        if not include_deleted and self._has_soft_delete():
            query = query.where(self.model_class.deleted_at.is_(None))
        
        if order_by:
            order_column = getattr(self.model_class, order_by, None)
            if order_column:
                query = query.order_by(order_column.desc() if order_desc else order_column.asc())
        
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_paginated(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = "id",
        order_desc: bool = True,
        include_deleted: bool = False,
    ) -> Tuple[List[ModelType], int]:
        """分页查询（带总数统计）"""
        base_query = select(self.model_class)
        count_query = select(func.count()).select_from(self.model_class)
        
        if filters:
            conditions = [
                getattr(self.model_class, key) == value
                for key, value in filters.items()
            ]
            base_query = base_query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))
        
        if not include_deleted and self._has_soft_delete():
            soft_delete_condition = self.model_class.deleted_at.is_(None)
            base_query = base_query.where(soft_delete_condition)
            count_query = count_query.where(soft_delete_condition)
        
        if order_by:
            order_column = getattr(self.model_class, order_by, None)
            if order_column:
                base_query = base_query.order_by(
                    order_column.desc() if order_desc else order_column.asc()
                )
        
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0
        
        offset_val = (page - 1) * page_size
        base_query = base_query.offset(offset_val).limit(page_size)
        
        result = await db.execute(base_query)
        items = list(result.scalars().all())
        
        logger.debug(
            f"[{self.model_class.__name__}] 分页查询: "
            f"page={page}, size={page_size}, total={total}, 返回={len(items)} 条"
        )
        
        return items, total

    async def create(
        self,
        db: AsyncSession,
        data: Union[Dict[str, Any], Any],
        *,
        auto_commit: bool = True,
        auto_refresh: bool = True,
    ) -> ModelType:
        """创建单条记录"""
        try:
            if isinstance(data, BaseModel):
                obj_data = data.model_dump()
            else:
                obj_data = data
            
            db_obj = self.model_class(**obj_data)
            db.add(db_obj)
            
            if auto_commit:
                await db.commit()
                
                if auto_refresh:
                    await db.refresh(db_obj)
            
            logger.info(
                f"[{self.model_class.__name__}] ✅ 创建成功: id={getattr(db_obj, 'id', 'N/A')}"
            )
            
            return db_obj
            
        except Exception as e:
            logger.error(f"[{self.model_class.__name__}] ❌ 创建失败: {e}")
            await db.rollback()
            raise

    async def bulk_create(
        self,
        db: AsyncSession,
        items: List[Union[Dict[str, Any], Any]],
        *,
        batch_size: int = 100,
        auto_commit: bool = True,
    ) -> List[ModelType]:
        """批量创建记录（高性能版本）"""
        created_objects = []
        
        try:
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                
                db_objects = []
                for item in batch:
                    if isinstance(item, BaseModel):
                        obj_data = item.model_dump()
                    else:
                        obj_data = item
                    
                    db_obj = self.model_class(**obj_data)
                    db_objects.append(db_obj)
                
                db.add_all(db_objects)
                
                if auto_commit:
                    await db.commit()
                    
                    for db_obj in db_objects:
                        await db.refresh(db_obj)
                
                created_objects.extend(db_objects)
            
            logger.info(
                f"[{self.model_class.__name__}] ✅ 批量创建成功: 共 {len(created_objects)} 条"
            )
            
            return created_objects
            
        except Exception as e:
            logger.error(f"[{self.model_class.__name__}] ❌ 批量创建失败: {e}")
            await db.rollback()
            raise

    async def update(
        self,
        db: AsyncSession,
        id: int,
        data: Union[Dict[str, Any], Any],
        *,
        auto_commit: bool = True,
        auto_refresh: bool = True,
    ) -> Optional[ModelType]:
        """根据ID更新记录"""
        try:
            if isinstance(data, BaseModel):
                obj_data = data.model_dump(exclude_unset=True)
            else:
                obj_data = data
            
            db_obj = await self.get_by_id(db, id)
            if not db_obj:
                logger.warning(f"[{self.model_class.__name__}] 更新失败: id={id} 不存在")
                return None
            
            for field, value in obj_data.items():
                setattr(db_obj, field, value)
            
            if auto_commit:
                await db.commit()
                if auto_refresh:
                    await db.refresh(db_obj)
            
            logger.info(
                f"[{self.model_class.__name__}] ✅ 更新成功: id={id}, "
                f"更新字段: {list(obj_data.keys())}"
            )
            
            return db_obj
            
        except Exception as e:
            logger.error(f"[{self.model_class.__name__}] ❌ 更新失败 (id={id}): {e}")
            await db.rollback()
            raise

    async def bulk_update(
        self,
        db: AsyncSession,
        updates: List[Tuple[int, Dict[str, Any]]],
        *,
        auto_commit: bool = True,
    ) -> int:
        """批量更新记录（使用 UPDATE 语句，高性能）"""
        try:
            updated_count = 0
            
            for record_id, data in updates:
                stmt = (
                    update(self.model_class)
                    .where(self.model_class.id == record_id)
                    .values(**data)
                )
                result = await db.execute(stmt)
                updated_count += result.rowcount
            
            if auto_commit:
                await db.commit()
            
            logger.info(
                f"[{self.model_class.__name__}] ✅ 批量更新成功: 共 {updated_count} 条"
            )
            
            return updated_count
            
        except Exception as e:
            logger.error(f"[{self.model_class.__name__}] ❌ 批量更新失败: {e}")
            await db.rollback()
            raise

    async def delete(
        self,
        db: AsyncSession,
        id: int,
        *,
        hard_delete: bool = False,
        auto_commit: bool = True,
    ) -> bool:
        """删除记录（默认软删除）"""
        try:
            if hard_delete:
                stmt = delete(self.model_class).where(self.model_class.id == id)
                result = await db.execute(stmt)
                success = result.rowcount > 0
            elif self._has_soft_delete():
                db_obj = await self.get_by_id(db, id)
                if not db_obj:
                    return False
                
                setattr(db_obj, "deleted_at", datetime.utcnow())
                success = True
            else:
                stmt = delete(self.model_class).where(self.model_class.id == id)
                result = await db.execute(stmt)
                success = result.rowcount > 0
            
            if auto_commit:
                await db.commit()
            
            action = "硬删除" if hard_delete else "软删除"
            logger.info(
                f"[{self.model_class.__name__}] ✅ {action}成功: id={id}"
            )
            
            return success
            
        except Exception as e:
            logger.error(f"[{self.model_class.__name__}] ❌ 删除失败 (id={id}): {e}")
            await db.rollback()
            raise

    async def exists(
        self,
        db: AsyncSession,
        *,
        filters: Dict[str, Any],
        exclude_id: Optional[int] = None,
    ) -> bool:
        """检查记录是否存在（高效版本，只查 COUNT）"""
        query = select(func.count()).select_from(self.model_class)
        
        conditions = [getattr(self.model_class, k) == v for k, v in filters.items()]
        
        if exclude_id:
            conditions.append(self.model_class.id != exclude_id)
        
        query = query.where(and_(*conditions))
        
        result = await db.execute(query)
        count = result.scalar() or 0
        
        return count > 0

    async def count(
        self,
        db: AsyncSession,
        *,
        filters: Optional[Dict[str, Any]] = None,
    ) -> int:
        """统计符合条件的记录数量"""
        query = select(func.count()).select_from(self.model_class)
        
        if filters:
            conditions = [getattr(self.model_class, k) == v for k, v in filters.items()]
            query = query.where(and_(*conditions))
        
        query = query.where(self.model_class.deleted_at.is_(None))
        
        result = await db.execute(query)
        return result.scalar() or 0


class TenantAwareRepository(BaseRepository[ModelType]):
    """
    多租户感知的 Repository
    
    自动在所有查询中注入 tenant_id 过滤条件，
    确保不同租户之间的数据隔离。
    
    Usage:
        class UserRepository(TenantAwareRepository[User]):
            model_class = User
            
        # 所有查询都会自动加上 WHERE tenant_id = ?
        users = await repo.get_all(db)  # 只返回当前租户的用户
    """

    async def _get_tenant_id(self) -> int:
        """获取当前请求的租户 ID（从 ContextVar）"""
        from app.core.tenant_context import get_tenant_id
        tid = get_tenant_id()
        if not tid:
            raise ValueError("未找到当前租户 ID，请确保多租户中间件正常工作")
        return tid

    async def get_by_id(self, db: AsyncSession, id: int, **kwargs) -> Optional[ModelType]:
        tenant_id = await self._get_tenant_id()
        result = await super().get_by_id(db, id, **kwargs)
        if result and hasattr(result, 'tenant_id') and result.tenant_id != tenant_id:
            return None
        return result

    async def get_all(self, db: AsyncSession, **kwargs) -> List[ModelType]:
        tenant_id = await self._get_tenant_id()
        filters = kwargs.get('filters', {}) or {}
        filters['tenant_id'] = tenant_id
        kwargs['filters'] = filters
        return await super().get_all(db, **kwargs)

    async def create(self, db: AsyncSession, data, **kwargs) -> ModelType:
        tenant_id = await self._get_tenant_id()
        if isinstance(data, dict):
            data['tenant_id'] = tenant_id
            return await super().create(db, data, **kwargs)
        elif isinstance(data, BaseModel):
            obj_dict = data.model_dump()
            obj_dict['tenant_id'] = tenant_id
            return await super().create(db, obj_dict, **kwargs)
        return await super().create(db, data, **kwargs)

    async def get_paginated(self, db: AsyncSession, **kwargs) -> Tuple[List[ModelType], int]:
        tenant_id = await self._get_tenant_id()
        filters = kwargs.get('filters', {}) or {}
        filters['tenant_id'] = tenant_id
        kwargs['filters'] = filters
        return await super().get_paginated(db, **kwargs)

    async def count(self, db: AsyncSession, **kwargs) -> int:
        tenant_id = await self._get_tenant_id()
        filters = kwargs.get('filters', {}) or {}
        filters['tenant_id'] = tenant_id
        kwargs['filters'] = filters
        return await super().count(db, **kwargs)