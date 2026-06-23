"""演示：LLM 编排器（supervisor）自主调用 SQL + 分析工具回答问题。

用法：
    uv run scripts/demos/orchestrate.py
    uv run scripts/demos/orchestrate.py "各品类销售额占比，占比最高的是哪个？"
"""

import sys

from langfuse import get_client

from insight.agents.agent_tools import CHART_KEY, make_analyst_tool, make_sql_tool
from insight.agents.critic_agent import CriticAgent
from insight.agents.orchestrator import Orchestrator
from insight.config import get_settings
from insight.paths import PROJECT_ROOT
from insight.tools.code_exec import DockerCodeExecutor
from insight.tools.db import Database
from insight.tools.llm import get_chat_client
from insight.agents.report_agent import ReportAgent

DEFAULT_QUESTION = "把各品类的总销售额画成柱状图，并指出销售额最高的品类。"


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION

    settings = get_settings()
    client = get_chat_client(settings)
    model = settings.chat_model
    db = Database(settings.db_path)
    executor = DockerCodeExecutor()

    orchestrator = Orchestrator(
        client=client,
        model=model,
        tools=[
            make_sql_tool(client, model, db),
            make_analyst_tool(client, model, executor),
        ],
        critic=CriticAgent(client, model),
        report=ReportAgent(client, model),  # ← 专门写结构化报告
    )

    print(f"❓ 问题：{question}\n")
    result = orchestrator.run(question)

    print("🧭 编排轨迹（自主调了哪些工具）：")
    for i, call in enumerate(result.tool_calls, 1):
        print(f"  {i}. {call['name']}({call['args']})")
    print(
        f"\n💬 最终回答（{result.steps} 步，{result.reviews} 轮审查）：\n{result.answer}"
    )

    png = orchestrator.workspace.get(CHART_KEY)
    if png:
        out = PROJECT_ROOT / "chart.png"
        out.write_bytes(png)
        print(f"\n🖼️ 图已保存：{out}")

    get_client().flush()


if __name__ == "__main__":
    main()
