"""测试 make_analyst_tool：前置守卫 / 真实分析 / 图入 workspace。"""

import base64

from insight.agents.agent_tools import CHART_KEY, SQL_RESULT_KEY, make_analyst_tool
from insight.agents.analysis import CHART_MARKER
from insight.agents.orchestrator import Workspace
from insight.tools.code_exec import CodeExecutor, ExecutionResult


class FakeExecutor:
    """假执行器：忽略代码，返回预设 ExecutionResult。"""

    def __init__(self, result):
        self._result = result

    def run(self, code):
        return self._result


def test_analyst_tool_requires_data(fake_llm):
    """workspace 没数据 → 返回守卫提示，不报错。"""
    tool = make_analyst_tool(fake_llm([]), "m", CodeExecutor())
    result = tool.handler(Workspace(), question="随便分析")
    assert "run_sql" in result


def test_analyst_tool_analyzes_workspace_data(fake_llm):
    """从 workspace 取数 → 假 LLM 出 pandas 代码 → 真子进程算出结果。"""
    ws = Workspace()
    ws.put(SQL_RESULT_KEY, (["region", "total"], [("华东", 100), ("华北", 50)]))
    client = fake_llm(["print(int(df['total'].sum()))"])
    tool = make_analyst_tool(client, "m", CodeExecutor())

    result = tool.handler(ws, question="求 total 之和")

    assert "150" in result


def test_analyst_tool_stashes_chart_to_workspace(fake_llm):
    """分析产生图 → PNG 进 workspace、返回文本里不含 marker。"""
    fake_png = b"\x89PNGfake"
    stdout = f"占比最高是数码\n{CHART_MARKER}{base64.b64encode(fake_png).decode()}"
    ws = Workspace()
    ws.put(SQL_RESULT_KEY, (["c"], [("a",)]))
    tool = make_analyst_tool(
        fake_llm(["print('x')"]),
        "m",
        FakeExecutor(ExecutionResult(True, stdout, "")),
    )

    result = tool.handler(ws, question="画图")

    assert ws.get(CHART_KEY) == fake_png
    assert "占比最高是数码" in result
    assert CHART_MARKER not in result
