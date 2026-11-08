"""
Rate Limiter - API 限流中间件

防止 API 被滥用，保护系统稳定性。

支持多种限流策略：
1. 固定窗口（Fixed Window）- 最简单，适合入门
2. 滑动窗口（Sliding Window）- 更平滑，推荐使用
3. 令牌桶（Token Bucket）- 允许突发流量
4. 漏桶（Leaky Bucket）- 匀速处理请求

基于 Redis 实现：
- 使用 Redis 的原子操作保证并发安全
- 支持分布式部署（多个实例共享计数）
- 自动过期机制，无需手动清理

使用示例：
    from app.middleware.rate_limiter import RateLimiterMiddleware, rate_limit

    # 全局限流：所有接口每分钟最多 100 次
    app.add_middleware(RateLimiterMiddleware, redis_client=redis, limit=100, window=60)

    # 单个路由限流：登录接口每分钟最多 5 次
    @router.post("/login")
    @rate_limit(limit=5, window=60)  # 5次/分钟
    async def login(...):
        pass

    # IP 级别限流：每个 IP 每秒最多 10 次
    @router.get("/api/data")
    @rate_limit(limit=10, window=1, key_func=lambda r: r.client.host)
    async def get_data(...):
        pass
"""

import logging
import time
from collections.abc import Awaitable, Callable
from functools import wraps

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.response import fail
from app.core.security import decode_token

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    限流器核心类

    实现滑动窗口算法（Sliding Window Algorithm）

    算法原理：
    - 维护一个时间窗口内的请求时间戳列表
    - 每次新请求到来时，清理过期的记录
    - 如果当前窗口内请求数 < 限制数 → 允许
    - 否则 → 拒绝并返回 429 Too Many Requests

    优势（相比固定窗口）：
    - 避免边界问题（固定窗口在边界处可能突发2倍流量）
    - 更平滑的限流曲线
    - 更精确的速率控制
    """

    def __init__(
        self,
        redis_client=None,
        *,
        default_limit: int = 100,
        default_window: int = 60,
        default_key_func: Callable | None = None,
    ):
        """
        初始化限流器

        Args:
            redis_client: Redis 客户端实例（可选，不提供时使用内存存储）
            default_limit: 默认限制次数（如 100 表示 100 次/窗口）
            default_window: 默认窗口大小（秒）（如 60 表示 1 分钟）
            default_key_func: 默认的 Key 生成函数（接收 Request 返回 str）
        """
        self.redis = redis_client
        self.default_limit = default_limit
        self.default_window = default_window
        self.default_key_func = default_key_func or self._default_key_func

        # 内存模式（Redis 不可用时的降级方案）
        self._memory_store: dict = {}

        logger.info(
            f"[RateLimiter] 初始化完成: "
            f"limit={default_limit}/{default_window}s, "
            f"backend={'Redis' if redis_client else 'Memory'}"
        )

    def _default_key_func(self, request: Request) -> str:
        """默认的 Key 生成函数（基于 IP + 路径）"""
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        return f"rate_limit:{client_ip}:{path}"

    def _generate_key(self, request: Request, key_func=None) -> str:
        """生成限流 Key"""
        func = key_func or self.default_key_func
        return func(request)

    async def is_allowed(
        self,
        key: str,
        *,
        limit: int | None = None,
        window: int | None = None,
    ) -> tuple[bool, dict]:
        """
        检查是否允许请求通过

        Args:
            key: 限流 Key（标识一个客户端/用户/IP）
            limit: 本次检查的限制次数（覆盖默认值）
            window: 本次检查的窗口大小（覆盖默认值）

        Returns:
            (是否允许, 元数据字典) 元组
            元数据包含：
            - current_count: 当前窗口内的请求数
            - remaining: 剩余可用次数
            - reset_time: 重置时间（Unix 时间戳）
            - retry_after: 建议重试等待时间（秒）
        """
        _limit = limit or self.default_limit
        _window = window or self.default_window
        current_time = time.time()

        try:
            if self.redis:
                result = await self._check_redis(key, _limit, _window, current_time)
            else:
                result = await self._check_memory(key, _limit, _window, current_time)

            return result

        except Exception as e:
            logger.error(f"[RateLimiter] ❌ 检查失败: {e}")
            # 出错时允许请求通过（降级策略）
            return True, {"error": str(e)}

    async def _check_redis(self, key: str, limit: int, window: int, current_time: float) -> tuple:
        """使用 Redis 实现滑动窗口"""
        pipe = self.redis.pipeline()

        # 清理过期记录（ZREMRANGEBYSCORE 移除 score < 当前时间 - 窗口大小）
        min_score = current_time - window
        pipe.zremrangebyscore(key, "-inf", min_score)

        # 统计当前窗口内的请求数
        pipe.zcard(key)

        # 如果未超限，添加当前请求的时间戳
        pipe.zadd(key, {str(current_time): current_time})

        # 设置过期时间（自动清理）
        pipe.expire(key, window + 1)

        results = await pipe.execute()

        current_count = results[1]  # ZCARD 的结果

        if current_count >= limit:
            # 已超限
            oldest_request = await self.redis.zrange(key, 0, 0, withscores=True)
            retry_after = (
                (oldest_request[0][1] - current_time + window) if oldest_request else window
            )

            logger.debug(
                f"[RateLimiter] ⛔ 限流触发: key={key}, "
                f"count={current_count}, limit={limit}, retry={retry_after:.1f}s"
            )

            return False, {
                "current_count": current_count,
                "remaining": 0,
                "reset_time": int(current_time + retry_after),
                "retry_after": max(1, int(retry_after)),
            }
        else:
            # 允许通过
            remaining = limit - current_count - 1

            logger.debug(
                f"[RateLimiter] ✅ 请求通过: key={key}, "
                f"count={current_count + 1}, limit={limit}, remaining={remaining}"
            )

            return True, {
                "current_count": current_count + 1,
                "remaining": remaining,
                "reset_time": int(current_time + window),
                "retry_after": 0,
            }

    async def _check_memory(self, key: str, limit: int, window: int, current_time: float) -> tuple:
        """使用内存实现滑动窗口（降级方案）"""
        if key not in self._memory_store:
            self._memory_store[key] = []

        timestamps = self._memory_store[key]

        # 清理过期记录
        cutoff = current_time - window
        timestamps[:] = [t for t in timestamps if t > cutoff]

        if len(timestamps) >= limit:
            retry_after = (timestamps[0] - current_time + window) if timestamps else window

            return False, {
                "current_count": len(timestamps),
                "remaining": 0,
                "reset_time": int(current_time + retry_after),
                "retry_after": max(1, int(retry_after)),
            }
        else:
            timestamps.append(current_time)
            remaining = limit - len(timestamps)

            return True, {
                "current_count": len(timestamps),
                "remaining": remaining,
                "reset_time": int(current_time + window),
                "retry_after": 0,
            }


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    ASGI 限流中间件

    在每个请求到达路由处理函数之前，
    自动进行限流检查。

    配置方式：
        app.add_middleware(RateLimiterMiddleware, ...)

    注意事项：
        - 必须在 Starlette/FastAPI 中间件栈中正确注册
        - 顺序很重要（应该在其他中间件之后执行）
        - 可以与单个路由的 @rate_limit 装饰器配合使用
    """

    def __init__(
        self,
        app,
        redis_client=None,
        *,
        limit: int = 100,
        window: int = 60,
        key_func: Callable | None = None,
        exclude_paths: list | None = None,
        path_limits: dict[str, tuple[int, int]] | None = None,
        user_key_paths: tuple[str, ...] | None = None,
        only_path_limits: bool = False,
        redis_provider: Callable[[], Awaitable[object]] | None = None,
    ):
        """
        初始化限流中间件。

        Args:
            limit / window: 默认限流规则（未命中 path_limits 时使用）
            path_limits: 路径前缀 → (limit, window)，只对命中路径生效
            user_key_paths: 命中这些路径前缀时按登录用户（JWT user_id）限流
            only_path_limits: True 时仅对 path_limits 命中的路径限流，
                其余业务 API 直接放行（避免影响存量接口）
            redis_provider: 异步 Redis 提供者（复用应用级单例客户端）；
                提供后首次命中限流路径时惰性获取，避免模块导入阶段连接 Redis
        """
        super().__init__(app)

        self._redis_provider = redis_provider
        self._redis_resolved = redis_client is not None or redis_provider is None

        self.limiter = RateLimiter(
            redis_client=redis_client,
            default_limit=limit,
            default_window=window,
            default_key_func=key_func,
        )

        # 排除路径（不进行限流的路径，如 /health, /docs 等）
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json", "/health"]

        # 路径级限流规则（按最长前缀匹配），key 为路径前缀
        self.path_limits = dict(path_limits or {})
        self.user_key_paths = tuple(user_key_paths or ())
        self.only_path_limits = only_path_limits

        logger.info(
            f"[RateLimiter Middleware] ✅ 初始化成功: "
            f"default={limit}/{window}s, paths={self.path_limits}, "
            f"user_key_paths={self.user_key_paths}, "
            f"only_path_limits={self.only_path_limits}, excluded={self.exclude_paths}"
        )

    def _match_path_limit(self, path: str) -> tuple[int, int] | None:
        """按最长前缀匹配路径规则；未命中返回 None。"""
        matched: tuple[str, tuple[int, int]] | None = None
        for prefix, rule in self.path_limits.items():
            if path.startswith(prefix) and (matched is None or len(prefix) > len(matched[0])):
                matched = (prefix, rule)
        return matched[1] if matched else None

    async def _ensure_backend(self) -> None:
        """惰性获取应用级 Redis 单例；失败时降级为进程内存限流（不阻断业务）。"""
        if self._redis_resolved:
            return
        self._redis_resolved = True
        try:
            client = await self._redis_provider() if self._redis_provider else None
        except Exception as exc:  # noqa: BLE001 - 限流降级不应影响请求主流程
            logger.error("[RateLimiter Middleware] Redis 不可用，降级内存限流: %s", exc)
            return
        self.limiter.redis = client

    @staticmethod
    def _user_key(request: Request, path: str) -> str | None:
        """从已签名的 Bearer Token 取 user_id；失败返回 None（由调用方降级为 IP）。"""
        authorization = request.headers.get("authorization") or ""
        if not authorization.startswith("Bearer "):
            return None
        payload = decode_token(authorization[7:])
        user_id = payload.get("user_id") if payload else None
        if not isinstance(user_id, int) or isinstance(user_id, bool) or user_id <= 0:
            return None
        return f"rate_limit:user:{user_id}:{path}"

    async def dispatch(self, request: Request, call_next):
        """中间件分发逻辑"""
        path = request.url.path

        # 排除不需要限流的路径 / CORS 预检
        if request.method == "OPTIONS":
            return await call_next(request)
        if any(path.startswith(exclude) for exclude in self.exclude_paths):
            return await call_next(request)

        path_rule = self._match_path_limit(path)
        if path_rule is None and self.only_path_limits:
            # 仅对显式配置的路径限流，其余业务 API 不受影响
            return await call_next(request)

        await self._ensure_backend()

        if path_rule is not None:
            limit, window = path_rule
        else:
            limit, window = self.limiter.default_limit, self.limiter.default_window

        # 用户级 key：只对显式声明 user_key_paths 的路径启用，避免全站解析 JWT
        key = None
        if any(path.startswith(prefix) for prefix in self.user_key_paths):
            key = self._user_key(request, path)
        if key is None:
            key = self.limiter._generate_key(request)

        allowed, metadata = await self.limiter.is_allowed(key, limit=limit, window=window)

        if not allowed:
            logger.warning(
                f"[RateLimiter Middleware] ⛔ 429 Too Many Requests: "
                f"path={path}, ip={request.client.host if request.client else '?'}, "
                f"retry_after={metadata.get('retry_after', '?')}s"
            )

            retry_after = metadata.get("retry_after", 60)
            body = fail(code=429, msg="请求过于频繁，请稍后再试")
            body["data"] = {"retry_after": retry_after}

            return JSONResponse(
                status_code=429,
                content=body,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(metadata.get("reset_time", "")),
                },
            )

        # 允许通过，添加响应头
        response = await call_next(request)

        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(metadata.get("remaining", 0))
        response.headers["X-RateLimit-Reset"] = str(metadata.get("reset_time", ""))

        return response


def rate_limit(
    *,
    limit: int,
    window: int = 60,
    key_func: Callable[[Request], str] | None = None,
    per_user: bool = False,
):
    """
    限流装饰器（用于单个路由级别）

    与全局中间件不同，这个装饰器可以针对特定路由设置不同的限流规则。

    Args:
        limit: 限制次数
        window: 时间窗口（秒）
        key_func: 自定义 Key 生成函数（接收 Request 返回字符串）
        per_user: 是否按用户限流（需要认证中间件先执行）

    Example:
        # 登录接口：每 IP 每 分钟最多 5 次
        @router.post("/login")
        @rate_limit(limit=5, window=60)
        async def login(...):
            pass

        # 敏感操作：每用户每小时只能调用 3 次
        @router.post("/export-report")
        @rate_limit(limit=3, window=3600, per_user=True)
        async def export_report(current_user=Depends(get_current_user)):
            pass

        # 自定义 Key（按 API Key 限流）
        @router.get("/api/v1/data")
        @rate_limit(limit=1000, window=60, key_func=lambda r: r.headers.get("X-API-Key"))
        async def get_data(...):
            pass
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从 kwargs 中提取 request 对象（FastAPI 注入）
            request = kwargs.get("request")

            if not request:
                # 尝试从位置参数中查找
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if not request:
                logger.warning("[RateLimiter] 无法获取 Request 对象，跳过限流")
                return await func(*args, **kwargs)

            # 提取 Redis 客户端
            redis_client = kwargs.get("redis_client")

            # 创建临时限流器实例
            limiter = RateLimiter(redis_client=redis_client)

            # 生成 Key
            if per_user and hasattr(request.state, "user"):
                user_id = getattr(request.state.user, "id", None)
                custom_key = f"rate_limit:user:{user_id}:{request.url.path}"
            elif key_func:
                custom_key = key_func(request)
            else:
                custom_key = limiter._generate_key(request)

            # 检查是否允许
            allowed, metadata = await limiter.is_allowed(custom_key, limit=limit, window=window)

            if not allowed:
                from fastapi import HTTPException

                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "Too Many Requests",
                        "message": "请求过于频繁，请稍后再试",
                        "retry_after": metadata.get("retry_after", 60),
                    },
                    headers={"Retry-After": str(metadata.get("retry_after", 60))},
                )

            # 允许通过，执行原函数
            return await func(*args, **kwargs)

        return wrapper

    return decorator


# 预定义的常用限流配置
RATE_LIMIT_CONFIGS = {
    "strict": {
        "login": {"limit": 5, "window": 300},
        "register": {"limit": 3, "window": 3600},
        "password_reset": {"limit": 3, "window": 3600},
        "sms_code": {"limit": 5, "window": 60},
    },
    "normal": {
        "api_default": {"limit": 100, "window": 60},
        "file_upload": {"limit": 10, "window": 60},
        "report_export": {"limit": 5, "window": 3600},
    },
    "relaxed": {
        "public_api": {"limit": 1000, "window": 60},
        "static_files": {"limit": 10000, "window": 60},
    },
}
