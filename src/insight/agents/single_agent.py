"""单 agent 基线：一个 LLM + 两个原始工具(query_db/run_code)，自己完成
SQL→查库→分析→执行→报告→自评 全流程。用来和多智能体编排做 A/B 对比（同模型、同 schema_context）。
"""

import json

from langfuse import observe
from openai import OpenAI

from insight.agents.analysis import build_analysis_code, extract_chart
from insight.errors import SQLExecutionError

PREVIEW_ROWS = 20  # 回给 LLM 的预览行数；完整结果只进 df，不塞满上下文

SINGLE_AGENT_SYSTEM = """你是一名数据分析师，有两个工具：
- query_db(sql)：在只读数据库执行一条 SQLite 查询并返回结果。
- run_code(code)：在沙箱里执行 pandas 代码做进阶分析/画图；代码里有一个已加载的 DataFrame `df`（= 你最近一次 query_db 的**完整**结果，即便上面只预览了前若干行）；画图必须用 `emit_chart(fig)` 把图交回，**不要用 plt.savefig 或 plt.show**（那样图不会被捕获）。

请完成用户的分析问题：
1. 想清楚要查什么，调 query_db 取数（可多次）。
2. 需要进阶计算/画图时调 run_code。**df 里已是该次查询的完整数据，直接用 df（如 df.sort_values/df.head），切勿把数据手敲进代码**——手敲容易抄漏行、抄错数。
3. **你的步数有限**：核心数据齐了就**尽快写报告**，最多画 1–2 张关键图，不要反复美化或追加图表。
4. 输出结构化中文报告：① 直接结论 ② 关键数据支撑 ③ 图表说明 ④ 口径/局限说明。
5. 最后【自我反思】：报告里每个数字/结论是否都由查到的真实数据支撑？有没有臆造或偷换口径？发现问题就修正后再给最终报告。

只用查到的真实数据，不要臆造。下面是数据库结构与业务口径：
{schema_context}
"""

QUERY_DB_TOOL = {
    "type": "function",
    "function": {
        "name": "query_db",
        "description": "在只读数据库执行一条 SQLite 查询并返回结果。",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "一条 SQLite SELECT"}
            },
            "required": ["sql"],
        },
    },
}

RUN_CODE_TOOL = {
    "type": "function",
    "function": {
        "name": "run_code",
        "description": "在沙箱执行 pandas 代码；df=最近一次 query_db 的结果；画图用 emit_chart()。",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "pandas/matplotlib 代码"}
            },
            "required": ["code"],
        },
    },
}


class SingleAgent:
    def __init__(
        self, client: OpenAI, model: str, db, executor, schema_context="", max_steps=12
    ):
        self.client = client
        self.model = model
        self.db = db
        self.executor = executor
        self.schema_context = schema_context
        self.max_steps = max_steps
        self.last_result = None  # 最近一次 query_db 的 (列, 行)
        self.last_chart = None

    @observe(name="single-agent")
    def run(self, question: str) -> dict:
        messages = [
            {
                "role": "system",
                "content": SINGLE_AGENT_SYSTEM.format(
                    schema_context=self.schema_context
                ),
            },
            {"role": "user", "content": question},
        ]
        tools = [QUERY_DB_TOOL, RUN_CODE_TOOL]
        called = []
        for step in range(1, self.max_steps + 1):
            resp = self.client.chat.completions.create(
                model=self.model, temperature=0, messages=messages, tools=tools
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return {
                    "answer": msg.content or "",
                    "steps": step,
                    "tool_calls": called,
                }
            messages.append(self._assistant_msg(msg))
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                called.append({"name": tc.function.name, "args": args})
                result = self._run_tool(tc.function.name, args)
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )
        # 预算耗尽仍在调工具：兜底降级——拿已查到的数据强制写一版报告
        return {
            "answer": self._finalize(messages),
            "steps": self.max_steps,
            "tool_calls": called,
        }

    def _finalize(self, messages: list) -> str:
        """步数耗尽时的兜底：不带 tools 再调一次，强制基于已有数据写报告。"""
        messages.append(
            {
                "role": "user",
                "content": (
                    "已达到步数上限，不要再调用任何工具。请立即基于上面已经查到的"
                    "数据，输出最终结构化中文报告：① 直接结论 ② 关键数据支撑 "
                    "③ 图表说明 ④ 口径/局限说明。"
                ),
            }
        )
        # 不传 tools，逼它输出文字报告而非继续调用工具
        resp = self.client.chat.completions.create(
            model=self.model, temperature=0, messages=messages
        )
        return resp.choices[0].message.content or "（达到步数上限，且无法生成报告）"

    def _run_tool(self, name: str, args: dict) -> str:
        try:
            if name == "query_db":
                return self._query_db(args["sql"])
            if name == "run_code":
                return self._run_code(args["code"])
            return f"未知工具 {name}"
        except Exception as e:
            return f"工具 {name} 出错：{e}"

    def _query_db(self, sql: str) -> str:
        try:
            # 取较多行进 df（黑板），但只把预览回给 LLM——大中间表不塞满上下文
            columns, rows = self.db.run_query(sql, max_rows=1000)
        except SQLExecutionError as e:
            return f"SQL 执行失败：{e.db_message}"
        self.last_result = (columns, rows)
        n = len(rows)
        preview = "\n".join(str(r) for r in rows[:PREVIEW_ROWS])
        if n > PREVIEW_ROWS:
            note = (
                f"\n…(仅预览前 {PREVIEW_ROWS} 行；完整 {n} 行已载入 run_code 的 df，"
                "分析时直接用 df，勿手敲数据)"
            )
        elif n:
            note = "\n(以上为完整结果；run_code 里同样可用 df)"
        else:
            note = ""
        return f"列：{columns}\n返回 {n} 行：\n{preview}{note}"

    def _run_code(self, code: str) -> str:
        if self.last_result is None:
            return "还没有数据，请先 query_db。"
        columns, rows = self.last_result
        r = self.executor.run(build_analysis_code(columns, rows, code))
        if not r.success:
            return f"代码执行出错：{r.error}"
        text, png = extract_chart(r.stdout)
        if png:
            self.last_chart = png
        return f"{text}\n（已生成图表）" if png else text

    @staticmethod
    def _assistant_msg(msg) -> dict:
        return {
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in msg.tool_calls
            ],
        }
