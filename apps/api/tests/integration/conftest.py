"""集成测试环境守卫。

集成测试会真实读写数据库并创建/删除业务数据。若指向开发库，历史演示数据
（如种子学员已持有的长期卡片）会与测试用例互相干扰，造成"偶发失败"。

规则：集成测试只允许在库名包含 ``test`` 的数据库上运行。
"""

import pytest

from app.core.config import get_settings


def pytest_configure(config: pytest.Config) -> None:
    db_url = get_settings().DATABASE_URL
    db_name = db_url.rsplit("/", 1)[-1].split("?", 1)[0]
    if "test" not in db_name:
        raise pytest.UsageError(
            f"集成测试禁止使用非测试库：当前数据库为 {db_name!r}。\n"
            "请先初始化独立测试库：\n"
            "  bash scripts/init_test_db.sh\n"
            "然后带上 TEST_DATABASE_URL 运行：\n"
            "  TEST_DATABASE_URL=postgresql+asyncpg://<user>:<pass>@<host>:<port>/dance_saas_test \\\n"
            "    .venv/bin/python -m pytest tests/integration -q"
        )
