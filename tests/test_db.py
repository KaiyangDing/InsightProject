"""测试 Database 的只读护栏与错误包装。"""

import pytest

from insight.errors import SQLExecutionError


def test_run_query_returns_rows(sample_db):
    cols, rows = sample_db.run_query(
        "SELECT region, COUNT(*) FROM customers GROUP BY region"
    )
    assert ("华东", 2) in rows


def test_rejects_non_select(sample_db):
    """写操作应被只读护栏挡下。"""
    with pytest.raises(SQLExecutionError):
        sample_db.run_query("DELETE FROM customers")


def test_bad_sql_raises_sql_execution_error(sample_db):
    """无效 SQL 应被包装成 SQLExecutionError（而非裸 sqlite3 错误）。"""
    with pytest.raises(SQLExecutionError):
        sample_db.run_query("SELECT nonexistent_col FROM customers")
