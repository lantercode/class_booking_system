
from datetime import timedelta, datetime, timezone

from jose import jwt, JWTError
# 第一步：导入需要的模块（提示：bcrypt）
from passlib.context import CryptContext

from app.core.config import get_settings
settings = get_settings()

# 第二步：创建 CryptContext 实例（提示：指定算法为 bcrypt）
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

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
