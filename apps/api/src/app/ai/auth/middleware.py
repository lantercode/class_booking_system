"""
鉴权中间件
职责：JWT 解析、角色校验、租户隔离
"""

from app.ai.context import ToolContext


class AuthMiddleware:
    """
    Tool 鉴权中间件

    每个 Tool 调用前执行：
    1. 解析 JWT Token
    2. 校验角色权限
    3. 注入 user_id / tenant_id / role
    """

    async def authenticate(self, token: str) -> ToolContext:
        """
        解析 Token，生成上下文

        Args:
            token: JWT Token

        Returns:
            ToolContext
        """
        # TODO: 接入真实的 JWT 解析逻辑
        # from app.core.auth import decode_token
        # payload = decode_token(token)

        # 临时返回假数据
        return ToolContext(
            user_id=1,
            tenant_id=1,
            role="student"
        )

    def check_permission(self, ctx: ToolContext, required_role: str) -> bool:
        """
        校验权限

        Args:
            ctx: 工具调用上下文
            required_role: 需要的角色

        Returns:
            是否有权限
        """
        # admin 拥有所有权限
        if ctx.is_admin():
            return True

        # 角色匹配
        return ctx.role == required_role
