"""
Membership Card Router - 会员卡模块路由

包含：
- 产品管理（CRUD）
- 会员卡管理（发放、查询、冻结、解冻）
- 消费流水查询
- 冻结记录查询
"""

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.rbac import require_roles
from app.core.response import success
from app.deps.auth import get_current_user
from app.modules.membership.schemas import (
    MembershipCardCancelRequest,
    MembershipCardCreate,
    MembershipCardExtendRequest,
    MembershipCardFreezeRequest,
    MembershipCardProductCreate,
    MembershipCardProductResponse,
    MembershipCardProductUpdate,
    MembershipCardResponse,
    MembershipCardTransactionResponse,
)
from app.modules.membership.service import membership_card_service

router = APIRouter(prefix="/membership", tags=["会员卡管理"])


# ============================================================
# 产品管理
# ============================================================

@router.post("/products", response_model=dict, status_code=201, summary="创建会员卡产品")
@require_roles("admin", "super_admin")
async def create_product(
    data: MembershipCardProductCreate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """创建会员卡产品"""
    tenant_id = current_user.get("tenant_id")
    result = await membership_card_service.create_product(db, data, tenant_id)
    await db.commit()
    await db.refresh(result)
    return success(data=MembershipCardProductResponse.model_validate(result), msg="产品创建成功")


@router.get("/products", response_model=dict, summary="获取产品列表")
async def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    status: int | None = Query(None, description="状态：0下架/1上架（不传表示全部）"),
    card_type: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取产品列表"""
    tenant_id = current_user.get("tenant_id")
    result = await membership_card_service.list_products(
        db, tenant_id, status=status, card_type=card_type, page=page, page_size=page_size,
    )
    # Convert ORM models to Pydantic schemas
    items = [MembershipCardProductResponse.model_validate(p) for p in result["items"]]
    result["items"] = items
    return success(data=result)


@router.get("/products/{product_id}", response_model=dict, summary="获取产品详情")
async def get_product(
    product_id: int = Path(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取产品详情"""
    tenant_id = current_user.get("tenant_id")
    result = await membership_card_service.get_product(db, product_id, tenant_id)
    return success(data=MembershipCardProductResponse.model_validate(result))


@router.put("/products/{product_id}", response_model=dict, summary="更新产品")
@require_roles("admin", "super_admin")
async def update_product(
    product_id: int = Path(...),
    data: MembershipCardProductUpdate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """更新产品"""
    tenant_id = current_user.get("tenant_id")
    result = await membership_card_service.update_product(db, product_id, tenant_id, data)
    await db.commit()
    await db.refresh(result)
    return success(data=MembershipCardProductResponse.model_validate(result), msg="产品更新成功")


@router.delete("/products/{product_id}", response_model=dict, summary="删除产品")
@require_roles("admin", "super_admin")
async def delete_product(
    product_id: int = Path(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """删除产品（软删除：设置 deleted_at）"""
    tenant_id = current_user.get("tenant_id")
    await membership_card_service.delete_product(db, product_id, tenant_id)
    await db.commit()
    return success(msg="产品已删除")


@router.get("/products/recycle-bin", response_model=dict, summary="回收站列表")
@require_roles("admin", "super_admin")
async def list_deleted_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取回收站中的产品列表"""
    tenant_id = current_user.get("tenant_id")
    result = await membership_card_service.list_deleted_products(
        db, tenant_id, page=page, page_size=page_size,
    )
    items = [MembershipCardProductResponse.model_validate(p) for p in result["items"]]
    result["items"] = items
    return success(data=result)


@router.post("/products/{product_id}/restore", response_model=dict, summary="恢复产品")
@require_roles("admin", "super_admin")
async def restore_product(
    product_id: int = Path(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """从回收站恢复产品"""
    tenant_id = current_user.get("tenant_id")
    result = await membership_card_service.restore_product(db, product_id, tenant_id)
    await db.commit()
    await db.refresh(result)
    return success(data=MembershipCardProductResponse.model_validate(result), msg="产品已恢复")


# ============================================================
# 会员卡管理
# ============================================================

@router.post("/cards", response_model=dict, status_code=201, summary="发放会员卡")
@require_roles("admin", "super_admin")
async def issue_card(
    data: MembershipCardCreate = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """发放会员卡
    
    - 默认不允许重复发卡（allow_duplicate=False）
    - 如果学员已有同产品的有效卡，返回 409 Conflict
    - 续卡场景请设置 allow_duplicate=true
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"📥 收到发卡请求: student_id={data.student_id}, product_id={data.product_id}, allow_duplicate={data.allow_duplicate}")
    
    tenant_id = current_user.get("tenant_id")
    operator_id = current_user.get("user_id")
    result = await membership_card_service.issue_card(
        db, data, tenant_id, operator_id, allow_duplicate=data.allow_duplicate
    )
    await db.commit()
    await db.refresh(result)
    return success(data=MembershipCardResponse.model_validate(result), msg="会员卡发放成功")


@router.get("/cards", response_model=dict, summary="获取会员卡列表")
async def list_cards(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    student_id: int | None = Query(None),
    product_id: int | None = Query(None),
    card_type: str | None = Query(None),
    status: int | None = Query(None),
    keyword: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取会员卡列表"""
    tenant_id = current_user.get("tenant_id")
    result = await membership_card_service.list_cards(
        db, tenant_id, student_id=student_id, product_id=product_id,
        card_type=card_type, status=status, keyword=keyword, page=page, page_size=page_size,
    )
    # items 已经是 dict 格式，直接用 Pydantic 转换
    items = [MembershipCardResponse.model_validate(c) for c in result["items"]]
    result["items"] = items
    return success(data=result)


@router.get("/my-cards", response_model=dict, summary="获取我的会员卡（学员端）")
async def get_my_cards(
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取当前学员的有效会员卡（学员端专用）"""
    tenant_id = current_user.get("tenant_id")
    student_id = current_user.get("user_id")
    result = await membership_card_service.get_student_active_cards(db, student_id, tenant_id)
    items = [MembershipCardResponse.model_validate(c) for c in result]
    return success(data=items)


@router.get("/cards/{card_id}", response_model=dict, summary="获取会员卡详情")
async def get_card(
    card_id: int = Path(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取会员卡详情"""
    tenant_id = current_user.get("tenant_id")
    result = await membership_card_service.get_card(db, card_id, tenant_id)
    return success(data=MembershipCardResponse.model_validate(result))


@router.post("/cards/{card_id}/freeze", response_model=dict, summary="冻结会员卡")
@require_roles("admin", "super_admin")
async def freeze_card(
    card_id: int = Path(...),
    data: MembershipCardFreezeRequest = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """冻结会员卡"""
    tenant_id = current_user.get("tenant_id")
    operator_id = current_user.get("user_id")
    result = await membership_card_service.freeze_card(
        db, card_id, tenant_id, data.reason, operator_id, data.freeze_days, data.auto_unfreeze
    )
    await db.commit()
    await db.refresh(result)
    return success(data=MembershipCardResponse.model_validate(result), msg="会员卡已冻结")


@router.post("/cards/{card_id}/unfreeze", response_model=dict, summary="解冻会员卡")
@require_roles("admin", "super_admin")
async def unfreeze_card(
    card_id: int = Path(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """解冻会员卡"""
    tenant_id = current_user.get("tenant_id")
    operator_id = current_user.get("user_id")
    result = await membership_card_service.unfreeze_card(db, card_id, tenant_id, operator_id)
    await db.commit()
    await db.refresh(result)
    return success(data=MembershipCardResponse.model_validate(result), msg="会员卡已解冻")


@router.post("/cards/{card_id}/extend", response_model=dict, summary="延长会员卡有效期")
@require_roles("admin", "super_admin")
async def extend_card(
    card_id: int = Path(...),
    data: MembershipCardExtendRequest = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """延长会员卡有效期（付费延期）"""
    tenant_id = current_user.get("tenant_id")
    operator_id = current_user.get("user_id")
    result = await membership_card_service.extend_card(
        db, card_id, tenant_id, data.extend_days, operator_id, data.remark or "付费延期"
    )
    await db.commit()
    await db.refresh(result)
    return success(data=MembershipCardResponse.model_validate(result), msg="有效期已延长")


@router.post("/cards/{card_id}/activate", response_model=dict, summary="激活会员卡（学员端）")
async def activate_card(
    card_id: int = Path(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """学员主动激活待激活的会员卡"""
    tenant_id = current_user.get("tenant_id")
    student_id = current_user.get("user_id")
    result = await membership_card_service.activate_card(db, card_id, tenant_id, student_id)
    await db.commit()
    await db.refresh(result)
    return success(data=MembershipCardResponse.model_validate(result), msg="会员卡已激活")


@router.post("/cards/{card_id}/admin-activate", response_model=dict, summary="管理员激活会员卡")
@require_roles("admin", "super_admin")
async def admin_activate_card(
    card_id: int = Path(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """管理员手动激活待激活的会员卡"""
    tenant_id = current_user.get("tenant_id")
    operator_id = current_user.get("user_id")
    result = await membership_card_service.admin_activate_card(db, card_id, tenant_id, operator_id)
    await db.commit()
    await db.refresh(result)
    return success(data=MembershipCardResponse.model_validate(result), msg="会员卡已激活")


@router.post("/cards/{card_id}/cancel", response_model=dict, summary="作废会员卡")
@require_roles("admin", "super_admin")
async def cancel_card(
    card_id: int = Path(...),
    data: MembershipCardCancelRequest = Body(...),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """作废会员卡（管理员操作）"""
    tenant_id = current_user.get("tenant_id")
    operator_id = current_user.get("user_id")
    result = await membership_card_service.cancel_card(
        db, card_id, tenant_id, data.reason, operator_id
    )
    await db.commit()
    await db.refresh(result)
    return success(data=MembershipCardResponse.model_validate(result), msg="会员卡已作废")


# ============================================================
# 消费流水
# ============================================================

@router.get("/transactions", response_model=dict, summary="获取消费流水列表")
async def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    card_id: int | None = Query(None),
    operation_type: str | None = Query(None),
    db: AsyncSession = Depends(get_session),
    current_user: dict = Depends(get_current_user),
):
    """获取消费流水列表"""
    tenant_id = current_user.get("tenant_id")
    result = await membership_card_service.list_transactions(
        db, tenant_id, card_id=card_id, operation_type=operation_type, page=page, page_size=page_size,
    )
    items = [MembershipCardTransactionResponse.model_validate(t) for t in result["items"]]
    result["items"] = items
    return success(data=result)