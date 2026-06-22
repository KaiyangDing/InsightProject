"""把子 agent 适配成编排器可调用的 Tool（agents-as-tools）。

每个 make_*_tool 工厂闭包住依赖（client/model/db…），返回一个 Tool。
大数据（表/图）写进 Workspace 共享，回给 LLM 的只是摘要——省上下文。
"""

from openai import OpenAI

from insight.agents.orchestrator import Tool, Workspace
from insight.agents.text2sql_agent import Text2SQLAgent
from insight.tools.db import Database

SQL_RESULT_KEY = "last_sql_result"  # workspace 里存最近一次 SQL 结果的 key


def make_sql_tool(client: OpenAI, model: str, db: Database) -> Tool:
    def handler(workspace: Workspace, question: str) -> str:
        result = Text2SQLAgent(client, model, db).run(question)
        if not result.success:
            return f"SQL 查询失败（自我纠错 {result.attempts} 次后）：{result.error}"

        columns, rows = result.result
        workspace.put(SQL_RESULT_KEY, (columns, rows))  # 真身放黑板，供下游 agent 取

        preview = "\n".join(str(r) for r in rows[:10])
        more = f"\n…(共 {len(rows)} 行，仅显示前 10 行)" if len(rows) > 10 else ""
        return (
            f"已执行 SQL：\n{result.output}\n\n"
            f"列：{columns}\n返回 {len(rows)} 行：\n{preview}{more}"
        )

    return Tool(
        name="run_sql",
        description=(
            "把一个自然语言取数问题转成 SQL 并在只读数据库上执行，返回查询到的数据。"
            "需要从数据库取具体数字或记录时调用；一次只问一个明确的问题。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "单一明确的自然语言取数问题（中文），如'每个品类的总销售额'。",
                }
            },
            "required": ["question"],
        },
        handler=handler,
    )
