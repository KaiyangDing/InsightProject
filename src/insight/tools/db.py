"""SQLite 数据访问层：连接、读取 schema、只读执行 SQL。

这是 agent 取数的唯一通道——统一在这里加只读保护、行数限制等。
agent 运行时永远只读；写库只发生在开发期的 init_db 脚本里。
"""

import sqlite3
import threading

from insight.paths import resolve
from insight.errors import DatabaseNotReadyError, SQLExecutionError


class Database:
    def __init__(self, db_path: str):
        self.db_path = resolve(db_path)  # 锚定到项目根，得到绝对 Path
        if not self.db_path.exists():
            raise DatabaseNotReadyError(
                f"找不到数据库 {self.db_path}，请先运行uv run生成。"
            )

    def _connect_ro(self) -> sqlite3.Connection:
        uri = f"{self.db_path.as_uri()}?mode=ro"  # as_uri 正确处理空格/盘符
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def get_schema_text(self) -> str:
        """返回所有表的建表语句(DDL)，用于喂给 LLM 理解库结构。"""
        with self._connect_ro() as conn:
            rows = conn.execute(
                "SELECT sql FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name"
            ).fetchall()
        return "\n\n".join(r["sql"] for r in rows if r["sql"])

    def run_query(
            self, sql: str, max_rows: int = 100, timeout_s: float = 10.0
    ) -> tuple[list[str], list[tuple]]:
        """只读执行一条 SELECT，返回 (列名, 数据行)，最多 max_rows 行。
        超时 timeout_s 秒会中断查询，防止病态 SQL（爆炸 join / 大排序）挂死。"""
        stripped = sql.strip().strip(";").lstrip().lower()
        if not (stripped.startswith("select") or stripped.startswith("with")):
            raise SQLExecutionError(sql, "只允许 SELECT/WITH 只读查询")
        try:
            with self._connect_ro() as conn:
                # interrupt() 可从其它线程安全调用，中断会让 execute/fetch 抛 OperationalError
                watchdog = threading.Timer(timeout_s, conn.interrupt)
                watchdog.start()
                try:
                    cur = conn.execute(sql)
                    columns = [d[0] for d in cur.description] if cur.description else []
                    rows = cur.fetchmany(max_rows)
                finally:
                    watchdog.cancel()
        except sqlite3.Error as e:
            raise SQLExecutionError(sql, f"{e}（疑似超过 {timeout_s}s 或语法错误）") from e
        return columns, [tuple(r) for r in rows]
