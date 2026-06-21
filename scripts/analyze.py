"""演示：SQL 取数 → 在 Docker 沙箱里用 pandas 做进阶分析。

用法：uv run scripts/analyze.py
"""

from langfuse import get_client

from insight.analysis import run_pandas_analysis
from insight.code_exec import DockerCodeExecutor
from insight.config import get_settings
from insight.db import Database
from insight.llm import get_chat_client
from insight.text2sql import build_messages, request_sql

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

    # 2) pandas 在 Docker 沙箱里做进阶分析（带自我纠错）
    result = run_pandas_analysis(
        client,
        settings.chat_model,
        DockerCodeExecutor(),
        ANALYSIS_QUESTION,
        columns,
        rows,
    )
    print(f"\n🐍 沙箱 pandas 代码（第 {result.attempts} 次尝试）：\n{result.code}")
    print("\n📈 分析结果：")
    if result.success:
        print(result.stdout)
    else:
        print(f"❌ 自我纠错 {result.attempts} 次后仍失败：\n{result.error}")

    get_client().flush()


if __name__ == "__main__":
    main()
