"""C：用 LLM-as-judge（qwen-max，跨模型减偏差）评 full orchestrator 在 Olist 上的报告质量。

用法：uv run scripts/eval/olist_judge.py  （Docker 开着以防触发分析；这些题基本只走 SQL→报告）
"""

from langfuse import get_client

from insight.agents.agent_tools import make_analyst_tool, make_sql_tool
from insight.agents.critic_agent import CriticAgent
from insight.agents.orchestrator import Orchestrator
from insight.agents.report_agent import ReportAgent
from insight.agents.schema_context import olist_schema_context, olist_overview
from insight.config import get_settings
from insight.eval.agent_eval import evaluate_agent, summarize
from insight.eval.judge import Judge
from insight.eval.olist_eval import OLIST_JUDGE_QUESTIONS
from insight.tools.code_exec import DockerCodeExecutor
from insight.tools.db import Database
from insight.tools.llm import get_chat_client

JUDGE_MODEL = "qwen-max"  # 跨模型裁判，减同源偏差（系统用 qwen-plus）


def main() -> None:
    settings = get_settings()
    client = get_chat_client(settings)
    model = settings.chat_model
    db = Database(settings.db_path)
    executor = DockerCodeExecutor()
    ctx = olist_schema_context(db.get_schema_text())

    def make_orchestrator() -> Orchestrator:
        return Orchestrator(
            client=client,
            model=model,
            tools=[
                make_sql_tool(client, model, db, schema_context=ctx),
                make_analyst_tool(client, model, executor),
            ],
            critic=CriticAgent(client, model),
            report=ReportAgent(client, model),
            schema_overview=olist_overview(),
        )

    judge = Judge(client, JUDGE_MODEL)
    questions = OLIST_JUDGE_QUESTIONS
    results = evaluate_agent(make_orchestrator, judge, questions)

    print(f"裁判 = {JUDGE_MODEL}（系统 = {model}）\n")
    for r in results:
        print(f"[忠实{r['faithfulness']} 相关{r['relevance']}] {r['question']}")
    s = summarize(results)
    print(
        f"\n📊 {s['n']} 题：忠实性均分 {s['avg_faithfulness']:.2f} / "
        f"相关性均分 {s['avg_relevance']:.2f}（满分 5）"
    )
    get_client().flush()


if __name__ == "__main__":
    main()
