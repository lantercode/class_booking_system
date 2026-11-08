"""Unit 测试隔离配置。

tests/conftest.py 中的 Redis ping / 数据库种子 fixture 是 session 级 autouse，
会递归作用于 tests/unit。单元测试必须保持“不依赖真实 DB / Redis”，
因此这里用同名 no-op fixture 覆盖父级实现（pytest 优先使用最近的 conftest）。
"""

import pytest


@pytest.fixture(scope="session", autouse=True)
def ensure_redis_available():
    """单元测试不连接 Redis。"""
    yield


@pytest.fixture(scope="session", autouse=True)
def seed_test_database():
    """单元测试不向数据库写入种子数据。"""
    yield
