"""
RBAC 权限系统使用示例

此文件展示如何在 FastAPI 路由中使用 RBAC 权限装饰器。
这不是实际的路由文件，而是参考示例。

实际使用时，请将装饰器添加到你的 router.py 文件中。
"""

from fastapi import APIRouter, Depends

# 导入 RBAC 装饰器
from app.core.rbac import require_permissions, require_roles

# 导入其他依赖
from app.deps.auth import get_current_user, get_optional_user
from app.core.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/example", tags=["RBAC 示例"])


# ═══════════════════════════════════════════════════════════════
# 示例1: 基于权限的访问控制（最常用）
# ═══════════════════════════════════════════════════════════════

@router.post("/users")
@require_permissions("user:create")  # ← 只有拥有 'user:create' 权限的用户才能调用
async def create_user(
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    创建用户接口
    
    权限要求:
        - user:create（创建用户权限）
        
    适用角色:
        - admin（管理员）- 通常有此权限
        
    不适用角色:
        - teacher（教师）- 通常没有此权限
        - student（学生）- 绝对没有此权限
    """
    # 业务逻辑：创建用户
    # 注意：这里不需要再写权限判断代码！装饰器已经处理了 ✅
    return {"message": "用户创建成功", "data": data}


@router.get("/users")
@require_permissions("user:read")  # ← 需要 'user:read' 权限
async def list_users(
    db: AsyncSession = Depends(get_db),
):
    """
    查看用户列表
    
    权限要求: user:read
    """
    return {"message": "返回用户列表"}


@router.put("/users/{user_id}")
@require_permissions("user:update", "user:read", require_all=True)  # ← 需要同时拥有两个权限
async def update_user(
    user_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    编辑用户信息
    
    权限要求（AND 逻辑）:
        - 必须同时拥有 user:update 和 user:read
        - 理由：编辑前需要能查看用户信息
    """
    return {"message": f"用户 {user_id} 更新成功"}


@router.delete("/users/{user_id}")
@require_permissions("user:delete")  # ← 高危操作，需要专门权限
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    删除用户（高危操作）
    
    权限要求: user:delete
    
    安全建议:
        - 此权限应该只分配给极少数管理员
        - 建议增加二次确认机制
        - 记录详细的审计日志
    """
    return {"message": f"用户 {user_id} 已删除"}


# ═══════════════════════════════════════════════════════════════
# 示例2: OR 逻辑（满足其一即可）
# ═══════════════════════════════════════════════════════════════

@router.get("/admin/reports")
@require_permissions("report:view", "admin:all", require_all=False)  # ← 有其中一个就行
async def view_reports(
    db: AsyncSession = Depends(get_db),
):
    """
    查看管理报表
    
    权限要求（OR 逻辑）:
        - 拥有 report:view（报表查看权限）或
        - 拥有 admin:all（管理员全部权限）
        
    适用场景:
        - 财务人员只有 report:view
        - 超级管理员有 admin:all
        - 两种人都能看报表
    """
    return {"message": "返回报表数据"}


# ═══════════════════════════════════════════════════════════════
# 示例3: 基于角色的访问控制（快速判断身份）
# ═══════════════════════════════════════════════════════════════

@router.get("/admin/dashboard")
@require_roles("admin", "super_admin")  # ← 管理员或超级管理员
async def admin_dashboard(
    db: AsyncSession = Depends(get_db),
):
    """
    管理员后台首页
    
    角色要求（OR 逻辑）:
        - admin 或 super_admin 角色
        
    使用场景:
        - 快速限制某些页面只能管理员访问
        - 不关心具体权限，只关心身份
    """
    return {"message": "欢迎来到管理后台"}


@router.get("/teacher/classes")
@require_roles("teacher", "admin")  # ← 教师或管理员都能查看
async def teacher_classes(
    db: AsyncSession = Depends(get_db),
):
    """
    教师的课程列表
    
    角色要求:
        - teacher（教师）可以查看自己的课程
        - admin（管理员）可以查看所有课程
    """
    return {"message": "返回课程列表"}


# ═══════════════════════════════════════════════════════════════
# 示例4: 组合使用（权限 + 角色 双重验证）
# ═══════════════════════════════════════════════════════════════

@router.post("/classes/{class_id}/grade")
@require_roles("teacher", "admin")  # 第一层：必须是教师或管理员
@require_permissions("grade:input")  # 第二层：必须有成绩录入权限
async def input_grade(
    class_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    录入学生成绩（双重验证）
    
    验证流程:
        1. 先检查角色：必须是 teacher 或 admin
        2. 再检查权限：必须有 grade:input 权限
        
    为什么需要双重验证?
        - 有些教师可能没有成绩录入权限（如外聘教师）
        - 有些管理员可能有此权限（如教务管理员）
        - 两层检查更安全、更灵活
    """
    return {"message": f"课程 {class_id} 成绩录入成功"}


# ═══════════════════════════════════════════════════════════════
# 示例5: 公开接口（无需权限）对比
# ═══════════════════════════════════════════════════════════════

@router.get("/public/classes")
async def public_classes(
    db: AsyncSession = Depends(get_db),
):
    """
    公开课程列表（无需登录）
    
    特点:
        - 没有 @require_permissions 装饰器
        - 没有 @require_roles 装饰器
        - 使用 get_optional_user（可选认证）而非 get_current_user
        
    适用场景:
        - 课程展示页
        - 学校介绍
        - 其他公开信息
    """
    return {"message": "返回公开课程列表"}


@router.get("/my-classes")
async def my_classes(
    current_user: dict = Depends(get_optional_user),  # 可选登录
    db: AsyncSession = Depends(get_db),
):
    """
    我的课程（登录后可看到个性化推荐）
    
    特点:
        - 无需强制登录（未登录也能查看）
        - 登录后可以看到个性化内容
        - 不需要特殊权限
    """
    if current_user:
        return {"message": f"返回用户 {current_user['user_id']} 的个性化课程"}
    else:
        return {"message": "返回默认课程列表（未登录状态）"}


# ═══════════════════════════════════════════════════════════════
# 完整的 CRUD 示例（预约管理模块）
# ═══════════════════════════════════════════════════════════════

booking_router = APIRouter(prefix="/bookings", tags=["预约管理"])


@booking_router.post("/")
@require_permissions("booking:create")
async def create_booking(data: dict):
    """创建预约 - 学生和教师都可以"""
    pass


@booking_router.get("/")
@require_permissions("booking:read")
async def list_bookings():
    """查看预约列表 - 管理员、教师、学生都有不同范围的读取权限"""
    pass


@booking_router.get("/{booking_id}")
@require_permissions("booking:read")
async def get_booking(booking_id: int):
    """查看预约详情"""
    pass


@booking_router.put("/{booking_id}")
@require_permissions("booking:update")
async def update_booking(booking_id: int, data: dict):
    """修改预约 - 通常只有本人或管理员"""
    pass


@booking_router.delete("/{booking_id}")
@require_permissions("booking:cancel")
async def cancel_booking(booking_id: int):
    """取消预约 - 高危操作，需要专门权限"""
    pass


@booking_router.post("/{booking_id}/approve")
@require_roles("teacher", "admin")  # 只有教师或管理员能审批
@require_permissions("booking:approve")
async def approve_booking(booking_id: int):
    """审批预约 - 双重验证"""
    pass


# ═══════════════════════════════════════════════════════════════
# 最佳实践总结
# ═══════════════════════════════════════════════════════════════
"""

"""
📋 RBAC 使用最佳实践：

1️⃣ 权限命名规范:
   - 格式: {资源}:{操作}
   - 资源用单数小写: user, class, booking
   - 操作用动词: create, read, update, delete, approve, export
   - 示例: user:create, class:update, booking:approve, report:export

2️⃣ 何时用 permissions vs roles:
   - 用 permissions 当你需要精确控制操作能力
     例: @require_permissions("user:delete")
   
   - 用 roles 当你只需要判断用户类型
     例: @require_roles("admin", "teacher")
   
   - 组合使用当需要双重保障
     例: @require_roles("teacher") + @require_permissions("grade:input")

3️⃣ AND vs OR 的选择:
   - require_all=True (AND): 高危操作需要多个权限
     例: 删除用户需要 [user:delete, user:read]
   
   - require_all=False (OR): 多种角色都能执行的操作
     例: 查看报表需要 [report:view] 或 [admin:all]

4️⃣ 性能优化建议:
   - Redis 缓存已内置，无需额外处理
   - 缓存 TTL 默认 5 分钟（可在 cache.py 中调整）
   - 权限变更时调用 clear_user_permission_cache() 清除缓存

5️⃣ 安全建议:
   - 危险操作（删除、导出敏感数据）使用专门的细粒度权限
   - 管理接口始终要求角色 + 权限双重验证
   - 定期审计权限分配情况
   - 记录权限拒绝日志（已自动记录在 checker.py 中）

"""
