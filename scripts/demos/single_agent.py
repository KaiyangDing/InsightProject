"""单 agent 基线 demo：一个 LLM + query_db/run_code 自己跑完整流程。

用法：uv run scripts/demos/single_agent.py "Olist 的销售额在各州如何分布？"
"""

import sys

from langfuse import get_client

from insight.agents.schema_context import olist_schema_context
from insight.agents.single_agent import SingleAgent
from insight.config import get_settings
from insight.tools.code_exec import DockerCodeExecutor
from insight.tools.db import Database
from insight.tools.llm import get_chat_client

DEFAULT = "Olist 的销售额在各个州是如何分布的？哪几个州最重要？"


def main() -> None:
    q = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    s = get_settings()
    client = get_chat_client(s)
    db = Database(s.db_path)
    agent = SingleAgent(
        client,
        s.chat_model,
        db,
        DockerCodeExecutor(),
        schema_context=olist_schema_context(db.get_schema_text()),
    )
    print(f"❓ {q}\n")
    r = agent.run(q)
    print("🧭 调用轨迹：")
    for i, c in enumerate(r["tool_calls"], 1):
        print(f"  {i}. {c['name']}({str(c['args'])[:90]})")
    print(f"\n💬 报告（{r['steps']} 步）：\n{r['answer']}")
    get_client().flush()


if __name__ == "__main__":
    main()
