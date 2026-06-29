"""
T02 测试配置 - 使用真实 HTTP 服务器进行集成测试

设计决策：
- 使用 httpx.AsyncClient + 真实 HTTP 服务器（而非 ASGITransport）
- 彻底解决 asyncpg/asyncio 事件循环冲突问题
- 更接近生产环境的测试方式
"""

import pytest
import asyncio
from redis.asyncio import Redis
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.core.config import get_settings
from app.main import app as fastapi_app
import threading
import time


settings = get_settings()
TEST_DATABASE_URL = settings.DATABASE_URL

# 全局变量存储服务器信息
_server_thread = None
_server_url = None


@pytest.fixture(scope="session")
def event_loop():
    """Session 级别的事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    if not loop.is_closed():
        loop.close()


@pytest.fixture(scope="session", autouse=True)
async def ensure_redis_available():
    """检查 Redis 可用性"""
    client = None
    try:
        client = Redis.from_url(settings.REDIS_URL, decode_responses=True)
        result = await client.ping()
        assert result is True
        print("\n✅ Redis 连接正常")
    finally:
        if client:
            await client.close()


@pytest.fixture(scope="session")
def live_server(event_loop):
    """
    启动真实的 Uvicorn 服务器用于测试
    
    这是解决 asyncpg 事件循环冲突的根本方案：
    - 真实的服务器进程有自己的事件循环
    - 完全隔离于测试进程的事件循环
    - 避免 ASGITransport 的各种兼容性问题
    """
    global _server_thread, _server_url
    
    import uvicorn
    from unittest.mock import patch
    
    # 随机端口避免冲突
    port = 8765
    _server_url = f"http://127.0.0.1:{port}"
    
    # 在后台线程中启动服务器
    def run_server():
        config = uvicorn.Config(
            fastapi_app,
            host="127.0.0.1",
            port=port,
            log_level="warning",  # 减少日志输出
        )
        server = uvicorn.Server(config)
        server.run()
    
    _server_thread = threading.Thread(target=run_server, daemon=True)
    _server_thread.start()
    
    # 等待服务器启动
    max_wait = 5  # 最大等待 5 秒
    start_time = time.time()
    while time.time() - start_time < max_wait:
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result == 0:
                print(f"\n🚀 测试服务器启动: {_server_url}")
                break
        except:
            pass
        time.sleep(0.1)
    else:
        raise RuntimeError(f"❌ 服务器在 {max_wait} 秒内未能启动")
    
    yield _server_url
    
    # 清理（daemon 线程会自动结束）
    _server_thread = None
    _server_url = None


@pytest.fixture(scope="function")
async def client(live_server):
    """
    Function 级别的 HTTP 客户端
    
    每个测试创建新的客户端连接到真实服务器
    """
    async with AsyncClient(base_url=live_server) as ac:
        yield ac


@pytest.fixture(scope="function")
async def db_session():
    """Function 级别的数据库会话 - 每个测试独立事务"""
    engine = None
    session = None
    
    try:
        engine = create_async_engine(
            TEST_DATABASE_URL,
            echo=False,
            pool_size=3,
            max_overflow=5,
            pool_pre_ping=True,
        )
        
        session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        
        session = session_factory()
        await session.begin()
        yield session
        
    finally:
        if session:
            try:
                await session.rollback()
            except Exception:
                pass
            finally:
                await session.close()
        
        if engine:
            try:
                await engine.dispose()
            except Exception:
                pass