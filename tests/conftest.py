"""pytest 夹具：每个测试用一个临时、独立、用完即弃的 SQLite 库。"""

import sqlite3

import pytest

from insight.db import Database


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
