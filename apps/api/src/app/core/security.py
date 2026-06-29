
from datetime import timedelta, datetime, timezone

from jose import jwt, JWTError
# 第一步：导入需要的模块（提示：bcrypt）
from passlib.context import CryptContext

from app.core.config import get_settings
settings = get_settings()

# 第二步：创建 CryptContext 实例（提示：指定算法为 bcrypt）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ==================== 密码相关 ====================

def hash_password(password: str) -> str:
    """
        密码哈希 - 将明文密码转换为不可逆的哈希值

        Args:
            password: 用户输入的明文密码

        Returns:
            哈希后的密码字符串
        """
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
        密码验证 - 验证用户输入的明文密码是否与哈希值匹配

        Args:
            plain_password: 用户输入的明文密码
            hashed_password: 已存储的哈希值

        Returns:
            如果密码匹配则返回 True，否则返回 False
        """
    return pwd_context.verify(plain_password, hashed_password)

# ==================== Access Token 相关 ====================

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
        创建访问令牌 - 生成用于访问 API 的访问令牌

        Args:
            data: 访问令牌包含的数据
            expires_delta: 令牌有效期，默认为 None

        Returns:
            访问令牌字符串
        """
    to_encode = data.copy()
    import uuid
    now = datetime.now(timezone.utc)
    to_encode["iat"] = now # 签发时间（确保唯一性）
    to_encode["jti"] = str(uuid.uuid4())
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")

def decode_token(token: str) -> dict | None:
    """
        解码令牌 - 解码访问令牌，获取令牌中的数据

        Args:
            token: 访问令牌字符串

        Returns:
            成功: 返回 payload 字典（包含 user_id, tenant_id 等）
            失败: 返回 None（Token 无效/过期/被篡改
        """
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        return None
    return payload

# ==================== Refresh Token 相关（新增）====================

def create_refresh_token(data: dict) -> str:
    """ 创建刷新令牌（7天有效） """
    import uuid
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    to_encode["iat"] = now # 签发时间（确保唯一性）
    to_encode["exp"] = now + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode["type"] = "refresh"
    to_encode["jti"] = str(uuid.uuid4())  # JWT ID（全局唯一标识符）
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")


# ==================== Token 黑名单相关（新增）====================

async def add_token_to_blacklist(token: str, redis) -> None:
    """ 将令牌加入黑名单 """
    if not settings.ENABLE_TOKEN_BLACKLIST:
        return
    key = f"{settings.REDIS_TOKEN_BLACKLIST_PREFIX}{token}"
    ttl = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    await redis.setex(key, ttl, "1")

async def is_token_blacklisted(token: str, redis) -> bool:
    """ 检查令牌是否在黑名单中 """
    if not settings.ENABLE_TOKEN_BLACKLIST:
        return False
    key = f"{settings.REDIS_TOKEN_BLACKLIST_PREFIX}{token}"
    return await redis.exists(key) == 1