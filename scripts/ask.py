"""text2SQL 演示（自我纠错 + Langfuse trace）：问题 → agent → 结果。

用法：
    uv run scripts/ask.py
    uv run scripts/ask.py "各地区有多少客户？"
"""

import sys

from langfuse import get_client

from insight.text2sql_agent import Text2SQLAgent
from insight.config import get_settings
from insight.db import Database
from insight.llm import get_chat_client

DEFAULT_QUESTION = "各品类的总销售额是多少？按从高到低排序。"


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION

    settings = get_settings()
    agent = Text2SQLAgent(
        client=get_chat_client(settings),
        model=settings.chat_model,
        db=Database(settings.db_path),
    )

    print(f"❓ 问题：{question}")
    result = agent.run(question)

    if result.success:
        columns, rows = result.result
        print(f"\n🧠 SQL（第 {result.attempts} 次尝试成功）：\n{result.output}")
        print("\n📊 查询结果：")
        print(columns)
        for row in rows:
            print(row)
        if not rows:
            print("（无数据）")
    else:
        print(f"\n❌ 自我纠错 {result.attempts} 次后仍失败：\n{result.error}")

    get_client().flush()


if __name__ == "__main__":
    main()
