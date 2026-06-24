"""text2SQL agent：自我纠错循环的 SQL 实现（继承 SelfCorrectingAgent）。

循环在 base._run，这里填三个钩子 + 带名字的 run。
可选 schema_context：传入则用"增强版 schema"，否则回退到 db 的裸 DDL。
"""

from langfuse import observe
from openai import OpenAI

from insight.agents.base import AgentResult, SelfCorrectingAgent
from insight.tools.db import Database
from insight.errors import SQLExecutionError
from insight.agents.text2sql import build_messages, request_sql


class Text2SQLAgent(SelfCorrectingAgent):
    def __init__(
        self,
        client: OpenAI,
        model: str,
        db: Database,
        max_attempts: int = 3,
        schema_context: str | None = None,
    ):
        super().__init__(max_attempts)
        self.client = client
        self.model = model
        self.db = db
        self.schema_context = schema_context

    @observe(name="text2sql-agent")
    def run(self, question: str) -> AgentResult:
        return self._run(question)

    def initial_messages(self, question: str) -> list[dict]:
        schema = (
            self.schema_context or self.db.get_schema_text()
        )  # 有增强用增强，否则裸 DDL
        return build_messages(question, schema)

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
