"""把子 agent 适配成编排器可调用的 Tool（agents-as-tools）。

每个 make_*_tool 工厂闭包住依赖（client/model/db…），返回一个 Tool。
大数据（表/图）写进 Workspace 共享，回给 LLM 的只是摘要——省上下文。
"""

from openai import OpenAI

from insight.agents.orchestrator import Tool, Workspace
from insight.agents.text2sql_agent import Text2SQLAgent
from insight.tools.db import Database
from insight.agents.analysis import extract_chart
from insight.agents.analysis_agent import CodeAnalysisAgent

SQL_RESULT_KEY = "last_sql_result"  # workspace 里存最近一次 SQL 结果的 key
CHART_KEY = "last_chart"  # workspace 里存最近一次分析产生的图（PNG bytes）


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


def make_analyst_tool(client: OpenAI, model: str, executor) -> Tool:
    def handler(workspace: Workspace, question: str) -> str:
        data = workspace.get(SQL_RESULT_KEY)
        if data is None:  # 前置条件守卫：还没取数
            return "还没有可分析的数据，请先用 run_sql 取数后再调用本工具。"

        columns, rows = data
        result = CodeAnalysisAgent(client, model, executor, columns, rows).run(question)
        if not result.success:
            return f"分析失败（自我纠错 {result.attempts} 次后）：{result.error}"

        text, png = extract_chart(result.result)  # result.result = 沙箱 stdout
        if png is not None:
            workspace.put(CHART_KEY, png)  # 图存黑板，不进 LLM 上下文
        note = "\n（已生成图表，保存在 workspace）" if png else ""
        return f"分析结果：\n{text}{note}"

    return Tool(
        name="analyze_data",
        description=(
            "对 run_sql 取到的数据做进阶分析：用 pandas 在安全沙箱里执行，"
            "可算占比/排序/聚合等，也能用 matplotlib 画图。"
            "必须先用 run_sql 取数后再调用本工具。"
        ),
        parameters={
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "对已取到的数据要做的分析或画图要求（中文）。",
                }
            },
            "required": ["question"],
        },
        handler=handler,
    )
