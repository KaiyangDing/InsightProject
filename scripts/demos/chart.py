"""演示：SQL 取数 → 沙箱里 matplotlib 画图 → 图片回传主机存盘。

用法：uv run scripts/chart.py
"""

from langfuse import get_client

from insight.agents.analysis import extract_chart
from insight.agents.analysis_agent import CodeAnalysisAgent
from insight.tools.code_exec import DockerCodeExecutor
from insight.config import get_settings
from insight.tools.db import Database
from insight.tools.llm import get_chat_client
from insight.paths import PROJECT_ROOT
from insight.agents.text2sql import build_messages, request_sql

SQL_QUESTION = "每个品类的总销售额"
CHART_QUESTION = "用柱状图展示各品类的总销售额（category 作 x 轴，total_sales 作 y 轴）"


def main() -> None:
    settings = get_settings()
    client = get_chat_client(settings)
    db = Database(settings.db_path)

    sql = request_sql(
        client, settings.chat_model, build_messages(SQL_QUESTION, db.get_schema_text())
    )
    columns, rows = db.run_query(sql)
    print(f"🗄️ SQL：{sql}\n📊 数据：{columns} {rows}")

    agent = CodeAnalysisAgent(
        client, settings.chat_model, DockerCodeExecutor(), columns, rows
    )
    result = agent.run(CHART_QUESTION)
    print(
        f"\n🐍 沙箱 matplotlib 代码（第 {result.attempts} 次尝试）：\n{result.output}"
    )

    if not result.success:
        print(f"\n❌ 失败：\n{result.error}")
        get_client().flush()
        return

    text, png = extract_chart(result.result)
    if text.strip():
        print(f"\n📈 文本输出：\n{text}")
    if png:
        out = PROJECT_ROOT / "chart.png"
        out.write_bytes(png)
        print(f"\n🖼️ 图已保存：{out}")
    else:
        print("\n（模型没调用 emit_chart，没有图）")

    get_client().flush()


if __name__ == "__main__":
    main()
