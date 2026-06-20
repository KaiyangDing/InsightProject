"""第一个 text2SQL 演示：自然语言问题 → LLM 生成 SQL → 只读执行 → 打印结果。

用法：
    uv run scripts/ask.py                  # 用默认问题
    uv run scripts/ask.py "各地区有多少客户？"   # 自定义问题
"""

import sys

from insight.config import get_settings
from insight.db import Database
from insight.llm import get_chat_client
from insight.text2sql import generate_sql

DEFAULT_QUESTION = "各品类的总销售额是多少？按从高到低排序。"


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION

    settings = get_settings()
    client = get_chat_client(settings)
    db = Database(settings.db_path)

    schema = db.get_schema_text()
    sql = generate_sql(client, settings.chat_model, question, schema)

    print(f"❓ 问题：{question}")
    print(f"\n🧠 生成的 SQL：\n{sql}")

    # 本版(a)：执行失败就直接打印错误，先看清 happy path 和错误长什么样。
    # 自我纠错（把错误喂回模型重试）留到下一步 2C。
    print("\n📊 查询结果：")
    try:
        columns, rows = db.run_query(sql)
        print(columns)
        for row in rows:
            print(row)
        if not rows:
            print("（无数据）")
    except Exception as e:
        print(f"❌ 执行失败：{e}")


if __name__ == "__main__":
    main()
