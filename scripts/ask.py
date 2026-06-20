"""text2SQL 演示（带自我纠错）：问题 → agent 循环（生成/执行/纠错） → 打印结果。

用法：
    uv run scripts/ask.py
    uv run scripts/ask.py "各地区有多少客户？"
"""

import sys

from insight.agent import Text2SQLAgent
from insight.config import get_settings
from insight.db import Database
from insight.errors import SQLExecutionError
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
    try:
        result = agent.run(question)
    except SQLExecutionError as e:
        print(f"\n❌ 自我纠错 {agent.max_attempts} 次后仍失败：\n{e}")
        return

    print(f"\n🧠 SQL（第 {result.attempts} 次尝试成功）：\n{result.sql}")
    print("\n📊 查询结果：")
    print(result.columns)
    for row in result.rows:
        print(row)
    if not result.rows:
        print("（无数据）")


if __name__ == "__main__":
    main()
