"""pytest 夹具与全局配置。"""

import os
import sqlite3

import pytest

from insight.tools.db import Database


def pytest_configure(config):
    """测试时关闭 Langfuse tracing：单元测试不依赖外部服务、也不往 dashboard 发噪声。

    pytest_configure 在收集测试（导入 agent/llm → 初始化 langfuse）之前执行，确保设置生效。
    """
    os.environ["LANGFUSE_TRACING_ENABLED"] = "false"


@pytest.fixture
def sample_db(tmp_path) -> Database:
    """建一个临时测试库（含 3 个客户），返回只读 Database 实例。

    tmp_path 是 pytest 内置夹具，每个测试一个独立临时目录，测完自动清理。
    """
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(db_file)
    conn.executescript(
        """
        CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, region TEXT);
        INSERT INTO customers (id, name, region) VALUES
            (1, '张伟', '华东'),
            (2, '李娜', '华东'),
            (3, '王芳', '华北');
        """
    )
    conn.commit()
    conn.close()
    return Database(str(db_file))
