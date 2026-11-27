"""Unit 测试隔离配置。

tests/conftest.py 中的 Redis ping fixture 是 session 级 autouse，
会递归作用于 tests/unit。部分单元测试（job_queue / 排期 / 会员卡迁移）
本身需要真实数据库，因此这里只屏蔽 Redis 依赖，**保留**父级的
``seed_test_database``：CI 空库需要它初始化租户/用户，否则依赖种子
数据的用例会抛 NoResultFound（本地因开发库已有种子而不会暴露）。
"""

import pytest


@pytest.fixture(scope="session", autouse=True)
def ensure_redis_available():
    """单元测试不连接 Redis。"""
    yield
