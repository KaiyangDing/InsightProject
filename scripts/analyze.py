"""演示：SQL 取数 → 在 Docker 沙箱里用 pandas 做进阶分析（自我纠错）。

用法：uv run scripts/analyze.py
"""

from langfuse import get_client

from insight.agents.analysis_agent import CodeAnalysisAgent
from insight.tools.code_exec import DockerCodeExecutor
from insight.config import get_settings
from insight.tools.db import Database
from insight.tools.llm import get_chat_client
from insight.agents.text2sql import build_messages, request_sql

SQL_QUESTION = "每个品类的总销售额"
ANALYSIS_QUESTION = "算出每个品类的销售额占总销售额的百分比，按占比从高到低排序"


def main() -> None:
    settings = get_settings()
    client = get_chat_client(settings)
    db = Database(settings.db_path)

    # 1) SQL 取基础数据
    sql = request_sql(
        client, settings.chat_model, build_messages(SQL_QUESTION, db.get_schema_text())
    )
    columns, rows = db.run_query(sql)
    print(f"🗄️ SQL：{sql}")
    print(f"📊 取到数据：{columns} {rows}")

    # 2) pandas 在 Docker 沙箱里做进阶分析（自我纠错）
    agent = CodeAnalysisAgent(
        client, settings.chat_model, DockerCodeExecutor(), columns, rows
    )
    result = agent.run(ANALYSIS_QUESTION)

    print(f"\n🐍 沙箱 pandas 代码（第 {result.attempts} 次尝试）：\n{result.output}")
    print("\n📈 分析结果：")
    if result.success:
        print(result.result)  # 成功时 result.result = stdout
    else:
        print(f"❌ 自我纠错 {result.attempts} 次后仍失败：\n{result.error}")

    get_client().flush()


if __name__ == "__main__":
    main()
