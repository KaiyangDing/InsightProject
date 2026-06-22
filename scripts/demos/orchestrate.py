"""演示：LLM 编排器（supervisor）自主调用 SQL 工具回答问题。

用法：
    uv run scripts/demos/orchestrate.py
    uv run scripts/demos/orchestrate.py "销售额最高的品类是哪个？大概多少？"
"""

import sys

from langfuse import get_client

from insight.agents.agent_tools import make_sql_tool
from insight.agents.orchestrator import Orchestrator
from insight.config import get_settings
from insight.tools.db import Database
from insight.tools.llm import get_chat_client
from insight.agents.critic import Critic  # 新增 import

DEFAULT_QUESTION = "哪个品类的总销售额最高？给出品类名和金额。"


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION

    settings = get_settings()
    client = get_chat_client(settings)
    db = Database(settings.db_path)

    orchestrator = Orchestrator(
        client=client,
        model=settings.chat_model,
        tools=[make_sql_tool(client, settings.chat_model, db)],
        critic=Critic(client, settings.chat_model),  # ← 挂上忠实性闸门
    )

    print(f"❓ 问题：{question}\n")
    result = orchestrator.run(question)

    print("🧭 编排轨迹（自主调了哪些工具）：")
    for i, call in enumerate(result.tool_calls, 1):
        print(f"  {i}. {call['name']}({call['args']})")
    print(
        f"\n💬 最终回答（{result.steps} 步，{result.reviews} 轮审查）：\n{result.answer}"
    )

    get_client().flush()


if __name__ == "__main__":
    main()
