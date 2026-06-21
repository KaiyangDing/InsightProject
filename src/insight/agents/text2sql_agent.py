"""text2SQL agent：自我纠错循环的 SQL 实现（继承 SelfCorrectingAgent）。

循环在 agent_base，这里只填三个钩子：建消息 / 生成 SQL / 执行 SQL。
"""

from openai import OpenAI

from insight.agents.agent_base import SelfCorrectingAgent
from insight.tools.db import Database
from insight.errors import SQLExecutionError
from insight.agents.text2sql import build_messages, request_sql


class Text2SQLAgent(SelfCorrectingAgent):
    def __init__(self, client: OpenAI, model: str, db: Database, max_attempts: int = 3):
        super().__init__(max_attempts)
        self.client = client
        self.model = model
        self.db = db

    def initial_messages(self, question: str) -> list[dict]:
        return build_messages(question, self.db.get_schema_text())

    def generate(self, messages: list[dict]) -> str:
        return request_sql(self.client, self.model, messages)

    def execute(self, sql: str) -> tuple[bool, object, str]:
        try:
            columns, rows = self.db.run_query(sql)
            return True, (columns, rows), ""
        except SQLExecutionError as e:
            return False, None, e.db_message

    def feedback(self, error: str) -> str:
        return f"上面的 SQL 执行报错：\n{error}\n请对照 schema 修正，只输出一条新的 SQLite 查询。"
