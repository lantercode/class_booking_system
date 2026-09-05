from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AuthException, ValidationException
from app.core.security import (
    add_token_to_blacklist,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_token_blacklisted,
    verify_password,
)
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    AuthResponse,
    LoginRequest,
    RegisterRequest,
    UserResponse,
    WechatLoginResponse,
)
from app.modules.auth.wechat_service import WechatService
from app.modules.user.models import UserStatus

settings = get_settings()


class AuthService:
    """认证服务 - 业务逻辑层"""
    @staticmethod
    async def update_current_user_profile(
        session: AsyncSession,
        user_id: int,
        data: dict,
    ) -> UserResponse:
        """
        更新当前登录用户的个人信息（学员端）

        限制：只能修改 nickname 和 avatar_url，不能修改敏感字段

        Args:
            session: 数据库会话
            user_id: 用户 ID
            data: 更新数据（只允许 nickname, avatar_url）

        Returns:
            更新后的用户信息

        Raises:
            AuthException: 用户不存在
        """
        user = await AuthRepository.get_user_by_id(session, user_id)
        if not user:
            raise AuthException("用户不存在")

        # 只允许修改的字段
        allowed_fields = ["nickname", "avatar_url"]
        update_data = {k: v for k, v in data.items() if k in allowed_fields and v is not None}

        if not update_data:
            raise ValidationException("没有可更新的字段")

        await AuthRepository.update_user(session, user, update_data)
        await session.commit()
        await session.refresh(user)

        return UserResponse(
            id=user.id,
            phone=user.phone,
            nickname=user.nickname or "",
            avatar=user.avatar_url,
            status=user.status,
            created_at=user.created_at,
        )

    @staticmethod
    async def get_current_user_profile(
        session: AsyncSession,
        user_id: int,
    ) -> UserResponse:
        """
        获取当前登录用户的完整信息

        Args:
            session: 数据库会话
            user_id: 用户 ID

        Returns:
            用户信息响应

        Raises:
            AuthException: 用户不存在
        """
        user = await AuthRepository.get_user_by_id(session, user_id)
        if not user:
            raise AuthException("用户不存在")
        return UserResponse(
            id=user.id,
            phone=user.phone,
            nickname=user.nickname or "",
            avatar=user.avatar_url,
            status=user.status,
            created_at=user.created_at,
        )

    @staticmethod
    async def register(
            session: AsyncSession,
            data: RegisterRequest
    ) -> AuthResponse:
        """
        用户注册

        Args:
            session: 数据库会话
            data: 注册请求数据

        Returns:
            认证响应（包含 Token 和用户信息）

        Raises:
            ValidationException: 手机号已存在/租户不存在等
        """
        # TODO: 实现用户注册逻辑
        # 根据 tenant_slug 查询租户 -- 系统中暂时默认了一个租户，所以前端都先默认这个租户所以一定能找到
        tenant = await AuthRepository.get_tenant_by_slug(session, data.tenant_slug)
        if not tenant:
            raise ValidationException("租户不存在")
        # 检查手机号是否已注册
        existing_user = await AuthRepository.get_user_by_phone(session, tenant.id, data.phone)
        if existing_user:
            raise ValidationException("手机号已存在")

        # 创建用户记录
        user_data = {
            "tenant_id": tenant.id,
            "phone": data.phone,
            "password_hash": hash_password(data.password),
            "nickname": data.nickname,
            "status": UserStatus.ACTIVE.value
        }

        user = await AuthRepository.create_user(session, user_data)

        # 分配默认角色 student
        student_role = await AuthRepository.get_role_by_code(
            session,
            "student",
            tenant.id
        )
        if student_role:
            await AuthRepository.assign_role(session, user.id, student_role.id)
        else:
            raise ValidationException("默认角色不存在")

        await session.commit() # 提交事务，确保数据持久化到数据库
        await session.refresh(user) # 刷新以获取数据库生成的值（如 id, created_at）

        # 生成双Token（Access Token + Refresh Token）
        token_data = {
            "user_id": user.id,
            "tenant_id": tenant.id,
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token({"user_id": user.id})

        # 返回认证响应 AuthResponse
        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse(
                id=user.id,
                phone=user.phone,
                nickname=user.nickname or "",
                status=user.status,
                created_at=user.created_at,
            )
        )

    @staticmethod
    async def login(
        session: AsyncSession,
        data: LoginRequest
    ) -> AuthResponse:
        """
        用户登录

        Args:
            session: 数据库会话
            data: 登录请求数据

        Returns:
            认证响应（包含 Token 和用户信息）

        Raises:
            ValidationException: 手机号/密码错误/账号已被禁用等
        """
        # TODO: 实现用户登录逻辑
        # 根据tenant_slug查询租户
        tenant = await AuthRepository.get_tenant_by_slug(session, data.tenant_slug)
        if not tenant:
            raise ValidationException(f"机构「{data.tenant_slug}」不存在，请检查机构标识")
        # 根据手机号查询用户（需要 tenant_id，但登录请求没有传租户id，所以可以根据租户标识符先查询到租户）
        user = await AuthRepository.get_user_by_phone(session, tenant.id, data.phone)
        if not user:
            raise AuthException("该手机号未注册，请检查账号或先注册")
        # 验证密码
        is_valid = verify_password(data.password, user.password_hash)
        if not is_valid:
            raise AuthException("密码错误，请重试")
        # 检查账号状态
        if user.status != UserStatus.ACTIVE.value:
            raise AuthException("该账号已被禁用，请联系管理员")
        # 更新最后登录时间
        await AuthRepository.update_user(session, user, {"last_login_at": datetime.now()})
        # 提交事务
        await session.commit()
        await session.refresh(user)
        # 生成双token
        token_data = {
            "user_id": user.id,
            "tenant_id": tenant.id,
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token({"user_id": user.id})
        # 返回认证响应 AuthResponse
        return AuthResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse(
                id=user.id,
                phone=user.phone,
                nickname=user.nickname or "",
                status=user.status,
                last_login_at=user.last_login_at,
                created_at=user.created_at
            )
        )

    @staticmethod
    async def logout(
        session: AsyncSession,
        user_id: int,
        refresh_token: str,
        redis_client,
    ) -> None:
        """
         用户登出

        功能：
        将 refresh_token 加入 Redis 黑名单，
        使其无法再用于刷新新的 access_token

        Args:
            session: 数据库会话（本方法可能不需要，但保持接口一致）
            user_id: 当前登录用户的 ID
            refresh_token: 要吊销的刷新令牌
            redis_client: Redis 客户端实例

        Returns:
            登出成功的消息字典

        Raises:
            AuthException: 如果 token 已经在黑名单中
        """
        # TODO 1: 检查 token 是否已经在黑名单中
        # 提示：调用 security.py 的 is_token_blacklisted() 函数
        # 如果已存在 → raise AuthException("Token 已失效")
        if redis_client:
            is_exist = await is_token_blacklisted(refresh_token, redis_client)
            if is_exist:
                raise AuthException("Token 已失效")

        # TODO 2: 将 token 加入黑名单
        # 提示：调用 security.py 的 add_token_to_blacklist() 函数
        if redis_client:
            await add_token_to_blacklist(refresh_token, redis_client)

        # TODO 3: 返回成功消息


    @staticmethod
    async def refresh_token(
        session: AsyncSession,
        current_refresh_token: str,
        redis_client,
    ) -> dict:
        """
        刷新访问令牌

        流程：
        1. 解码并验证 refresh_token (JWT)
        2. 检查 token 是否已被加入黑名单（是否已登出或已使用过）
        3. 从 token payload 中提取 user_id
        4. 查询数据库确认用户存在且状态正常
        5. 将当前的 refresh_token 加入黑名单（一次性使用）
        6. 生成新的 access_token + 新的 refresh_token
        7. 返回新的 Token 对

        Args:
            session: 数据库会话
            current_refresh_token: 当前的刷新令牌
            redis_client: Redis 客户端实例

        Returns:
            包含新 Token 的字典

        Raises:
            AuthException: Token 无效/已过期/已在黑名单中/用户不存在/账号被禁用
        """
        # TODO 1: 解码 JWT token 并验证
        # 提示：调用 security.py 的 decode_jwt() 或 jwt.decode()
        # 需要捕获 jwt.ExpiredSignatureError 和 jwt.InvalidTokenError
        # 如果解码失败 → raise AuthException("Token 无效或已过期")
        print("🔄 Step 1: 解码 Token...")
        decoded_payload = decode_token(current_refresh_token)
        if not decoded_payload:
            print("❌ Token 解码失败")
            raise AuthException("Token 无效或已过期")
        print(f"✅ Token 解码成功, user_id={decoded_payload.get('user_id')}")


        # TODO 2: 检查 token 是否在黑名单中
        # 提示：调用 is_token_blacklisted()
        # 如果在黑名单中 → raise AuthException("Token 已失效")
        print(f"🔄 Step 2: 检查黑名单 (redis_client={type(redis_client).__name__ if redis_client else None})...")
        if redis_client:
            is_exist = await is_token_blacklisted(current_refresh_token, redis_client)
            if is_exist:
                print("❌ Token 在黑名单中")
                raise AuthException("Token 已失效")
            print("✅ 黑名单检查通过")
        else:
            print("⚠️  Redis 客户端为空，跳过黑名单检查")

        # TODO 3: 提取 user_id
        # 提示：从 decoded_payload 中获取 "user_id" 字段
        # 如果没有 user_id → raise AuthException("无效的 Token")
        user_id = decoded_payload.get("user_id")
        if not user_id:
            raise AuthException("无效的 Token")

        # TODO 4: 查询用户信息
        # 提示：调用 AuthRepository.get_user_by_id(session, user_id)
        # 如果用户不存在 → raise AuthException("用户不存在")
        user = await AuthRepository.get_user_by_id(session, user_id)
        if not user:
            raise AuthException("用户不存在")

        # TODO 5: 检查用户状态
        # 提示：检查 user.status != UserStatus.ACTIVE.value
        # 如果被禁用 → raise AuthException("账号已被禁用")
        if user.status != UserStatus.ACTIVE.value:
            raise AuthException("账号已被禁用")

        # TODO 6: 将旧的 refresh_token 加入黑名单（关键步骤！）
        # 提示：调用 add_token_to_blacklist()
        # 这确保了 refresh_token 只能使用一次（旋转机制）
        print("🔄 Step 6: 将旧 Token 加入黑名单...")
        if redis_client:
            await add_token_to_blacklist(current_refresh_token, redis_client)
            print("✅ 已加入黑名单")
        else:
            print("⚠️  Redis 客户端为空，跳过加入黑名单")

        # TODO 7: 生成新的双 Token
        # 提示：调用 create_access_token() 和 create_refresh_token()
        # access_token payload: {"user_id": user.id, "tenant_id": user.tenant_id}
        # refresh_token payload: {"user_id": user.id}
        access_token = create_access_token(
            {"user_id": user.id, "tenant_id": user.tenant_id}
        )
        refresh_token = create_refresh_token({"user_id": user.id})

        # TODO 8: 构建并返回响应
        return {
            "access_token": access_token,  # ← 填入新生成的 access_token
            "refresh_token": refresh_token,  # ← 填入新生成的 refresh_token
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # 转换为秒
        }

    @staticmethod
    async def wechat_auto_login(
            session: AsyncSession,
            code: str,
            app_id: str,
            tenant_slug: str
    ) -> AuthResponse:
        if not app_id:
            app_id = settings.WECHAT_APP_ID
        # 获取openid
        wechat_data = WechatService.code_to_openid(code, app_id)
        print(f"wechat_data: {wechat_data}")
        openid = wechat_data['openid']
        # 获取租户
        tenant = await AuthRepository.get_tenant_by_slug(session, tenant_slug)
        if not tenant:
            raise AuthException("租户不存在")
        # 检查绑定状态
        wechat_account = await AuthRepository.get_wechat_account_by_openid(session, openid, app_id)
        # 如果已绑定
        if wechat_account:
            user = await AuthRepository.get_user_by_id(session, wechat_account.user_id)
            # 检查用户状态
            if user.status != UserStatus.ACTIVE.value:
                raise AuthException("账号已被禁用")
            # 生成双Token
            access_token = create_access_token({"user_id": user.id, "tenant_id": user.tenant_id})
            refresh_token = create_refresh_token({"user_id": user.id})
            return WechatLoginResponse(
                need_bind=False,
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer",
                expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user=UserResponse(
                    id=user.id,
                    phone=user.phone,
                    nickname=user.nickname or '',
                    status=user.status,
                    created_at=user.created_at
                )
            )
        else:
            session_key = wechat_data["session_key"]
            bind_token = create_access_token(
                {"openid": openid, "app_id": app_id, "session_key": session_key, "type": "bind"},
                timedelta(minutes=15),
            )
            return WechatLoginResponse(need_bind=True, bind_token=bind_token)

    @staticmethod
    async def wechat_bind(
        session: AsyncSession,
        bind_token: str,
        phone: str | None = None,
        encrypted_data: str | None = None,
        iv: str | None = None,
        tenant_slug: str = "",
    ) -> WechatLoginResponse:
        payload = decode_token(bind_token)
        if not payload or payload.get("type") != "bind":
            raise AuthException("绑定凭证无效或已过期")

        openid = payload["openid"]
        app_id = payload["app_id"]
        session_key = payload.get("session_key", "")

        tenant = await AuthRepository.get_tenant_by_slug(session, tenant_slug)
        if not tenant:
            raise AuthException("租户不存在")

        if encrypted_data and iv:
            if not session_key:
                raise AuthException("绑定凭证缺少会话密钥，请重新登录")
            phone = WechatService.decrypt_phone(encrypted_data, iv, session_key)
            print(f"微信手机号解密成功: {phone}")

        if not phone:
            raise AuthException("未获取到手机号，请授权后重试")

        user = await AuthRepository.get_user_by_phone(session, tenant.id, phone)
        if not user:
            return WechatLoginResponse(
                need_bind=True,
                bind_token=bind_token,
                decrypted_phone=phone,
                error_msg="该微信绑定的手机号未在系统中注册，请手动输入机构登记的手机号，或联系后台管理员",
            )

        if user.status != UserStatus.ACTIVE.value:
            raise AuthException("账号已被禁用，请联系管理员")

        await AuthRepository.create_wechat_account(session, {
            "user_id": user.id,
            "open_id": openid,
            "app_id": app_id,
        })

        await AuthRepository.update_user(session, user, {"last_login_at": datetime.now()})
        await session.commit()
        await session.refresh(user)

        access_token = create_access_token({"user_id": user.id, "tenant_id": user.tenant_id})
        refresh_token = create_refresh_token({"user_id": user.id})

        return WechatLoginResponse(
            need_bind=False,
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserResponse(
                id=user.id,
                phone=user.phone,
                nickname=user.nickname or "",
                status=user.status,
                created_at=user.created_at,
            ),
        )

    @staticmethod
    async def wechat_unbind(
        session: AsyncSession,
        user_id: int,
    ) -> dict:
        wechat_account = await AuthRepository.get_wechat_account_by_user_id(session, user_id)
        if not wechat_account:
            raise AuthException("该账号未绑定微信")

        await AuthRepository.delete_wechat_account(session, wechat_account)
        await session.commit()

        return {"msg": "微信已解绑", "unbind_at": datetime.now()}
