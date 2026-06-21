"""text2SQL agent：生成 → 执行 → 若报错把错误喂回模型改了重试（自我纠错循环）。

这是项目第一个 agent 循环：plan(生成) → act(执行) → observe(结果/错误) → 修正重试。
"""

from dataclasses import dataclass
from openai import OpenAI
from langfuse import observe

from insight.db import Database
from insight.errors import SQLExecutionError
from insight.text2sql import build_messages, request_sql


@dataclass
class Text2SQLResult:
    question: str
    sql: str
    columns: list[str]
    rows: list[tuple]
    attempts: int  # 一共试了几次（含首次）


class Text2SQLAgent:
    def __init__(self, client: OpenAI, model: str, db: Database, max_attempts: int = 3):
        self.client = client
        self.model = model
        self.db = db
        self.max_attempts = max_attempts

    @observe(name="text2sql-agent")
    def run(self, question: str) -> Text2SQLResult:
        schema = self.db.get_schema_text()
        messages = build_messages(question, schema)

        last_error: SQLExecutionError | None = None

        for attempt in range(1, self.max_attempts + 1):
            sql = request_sql(self.client, self.model, messages)
            try:
                columns, rows = self.db.run_query(sql)
                return Text2SQLResult(question, sql, columns, rows, attempt)
            except SQLExecutionError as e:
                last_error = e
                # 把"模型给的 SQL"和"执行报错"追加进对话，让它据此修正
                messages.append({"role": "assistant", "content": sql})
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"上面的 SQL 执行报错：\n{e.db_message}\n"
                            f"请对照 schema 修正，只输出一条新的 SQLite 查询。"
                        ),
                    }
                )
        # 预算用尽仍失败 → 抛出最后的错误（这类错 agent 没修好）
        raise last_error
