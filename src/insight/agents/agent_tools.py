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
SQL_ROW_CAP = 100  # 必须与 db.run_query 的默认 max_rows 一致；取满即视为"可能被截断"


def make_sql_tool(
    client: OpenAI, model: str, db: Database, schema_context=None
) -> Tool:
    def handler(workspace: Workspace, question: str) -> str:
        result = Text2SQLAgent(client, model, db, schema_context=schema_context).run(
            question
        )
        if not result.success:
            return f"SQL 查询失败（自我纠错 {result.attempts} 次后）：{result.error}"

        columns, rows = result.result
        workspace.put(SQL_RESULT_KEY, (columns, rows))  # 真身放黑板，供下游 agent 取

        n = len(rows)
        preview = "\n".join(str(r) for r in rows[:10])
        if n >= SQL_ROW_CAP:
            # 取满上限 = 极可能被截断。绝不能说"完整"，要把它赶回 SQL 里聚合，
            # 否则下游 analyze_data 会在残缺样本上统计、结果失真。
            more = (
                f"\n⚠️ 结果已达取数上限 {SQL_ROW_CAP} 行、**很可能被截断**，这不是完整数据。"
                f"\n若你要的是整体统计或按某维度分组对比，请改为让 run_sql **在 SQL 里直接聚合**"
                f"（GROUP BY 出每组统计量），不要拉原始明细再交给 analyze_data 分组。"
            )
        elif n > 10:
            # 未截断、但行数较多：真身已在 workspace，赶它去 analyze_data，别重复查。
            more = (
                f"\n…(此处仅预览前 10 行)。完整 {n} 行已存入工作区(workspace)。"
                f"\n⚠️ 若要对全部数据排序/聚合/对比/找极值/画图，请调用 analyze_data"
                f"（它能读到全部 {n} 行）；不要为了'看全数据'而重复 run_sql 同一张查询。"
            )
        else:
            more = ""
        return (
            f"已执行 SQL：\n{result.output}\n\n"
            f"列：{columns}\n返回 {n} 行：\n{preview}{more}"
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
