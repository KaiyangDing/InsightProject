"""项目自定义异常。区分"agent 能修的"和"该崩给开发者的"。"""


class InsightError(Exception):
    """项目所有自定义异常的基类。"""


class DatabaseNotReadyError(InsightError):
    """数据库不存在/未初始化——致命，需开发者先建库（agent 修不了）。"""


class SQLExecutionError(InsightError):
    """SQL 执行失败——agent 可恢复：带上 sql 和数据库原始报错，喂回模型重试。"""

    def __init__(self, sql: str, db_message: str):
        self.sql = sql
        self.db_message = db_message
        super().__init__(f"SQL 执行失败: {db_message}\nSQL: {sql}")
