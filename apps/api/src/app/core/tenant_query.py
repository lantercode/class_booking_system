"""
多租户查询自动注入 - SQLAlchemy 2.0 do_orm_execute 事件

功能：
- 自动为所有包含 tenant_id 字段的查询添加 WHERE 条件
- 防止开发者遗漏租户过滤导致数据泄露
- 支持跳过特定场景（如管理员跨租户查询）

技术原理：
- 使用 SQLAlchemy 2.0 的 SessionEvents.do_orm_execute 事件
- 在 ORM 查询执行前拦截并修改
- 动态检测查询涉及的实体并注入 WHERE tenant_id = :current_tenant_id 条件

兼容性：
- 仅支持 SQLAlchemy >= 2.0
- 替代已废弃的 before_compile 事件
"""

import logging
from typing import Optional

from sqlalchemy import event, true
from sqlalchemy.orm import Session, with_loader_criteria

from app.core.tenant_context import get_tenant_id

logger = logging.getLogger(__name__)


def _add_tenant_filter_to_orm_query(orm_context):
    """
    为 ORM 查询添加租户过滤条件（SQLAlchemy 2.0 方式）

    Args:
        orm_context: ORM 执行上下文对象

    注意：
        此函数不应返回值，而是直接修改 orm_context.statement
        因为 SQLAlchemy 会对返回值进行布尔判断，导致 TypeError
    """
    current_tenant_id = get_tenant_id()

    # 如果没有当前租户 ID（如未认证请求），跳过
    if not current_tenant_id:
        logger.debug("[Tenant Query] No current tenant_id, skip injection")
        return

    statement = orm_context.statement
    
    # 获取查询涉及的所有实体类
    entities_to_filter = []

    # 检查 statement 的描述符
    if hasattr(statement, 'column_descriptions'):
        for desc in statement.column_descriptions:
            entity = desc.get('entity')
            if entity and hasattr(entity, 'tenant_id'):
                entities_to_filter.append(entity)

    # 如果没有找到任何实体，跳过
    if not entities_to_filter:
        return

    # 为每个有 tenant_id 的实体应用过滤条件
    modified_statement = statement
    for entity in set(entities_to_filter):  # 去重
        modified_statement = modified_statement.options(
            with_loader_criteria(
                entity,
                lambda cls, tid=current_tenant_id: cls.tenant_id == tid,
                include_aliases=True,
                propagate_to_loaders=True
            )
        )

    # 直接修改 orm_context，不返回值！
    orm_context.statement = modified_statement
    
    logger.debug(f"[Tenant Query] Injected tenant_id={current_tenant_id} for {len(set(entities_to_filter))} entity(ies)")


def setup_tenant_query_injection(session_factory=None):
    """
    注册多租户查询自动注入事件监听器（SQLAlchemy 2.0 版本）

    应在应用启动时调用一次（如 main.py 中）

    Args:
        session_factory: 可选的数据库会话工厂（用于绑定事件到特定 Session 类）
    """
    if session_factory:
        event.listen(session_factory, "do_orm_execute", _add_tenant_filter_to_orm_query)
    else:
        # 如果没有提供 session_factory，监听全局 Session 类
        event.listen(Session, "do_orm_execute", _add_tenant_filter_to_orm_query)

    logger.info("[Tenant Query] Auto-injection enabled (SQLAlchemy 2.0 mode)")