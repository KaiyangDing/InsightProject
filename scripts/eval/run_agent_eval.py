"""跑多智能体端到端评测：编排器答一组问题 → LLM-as-judge 打分 → 输出均分。

用法：uv run scripts/eval/run_agent_eval.py
"""

from langfuse import get_client

from insight.agents.agent_tools import make_analyst_tool, make_sql_tool
from insight.agents.critic_agent import CriticAgent
from insight.agents.orchestrator import Orchestrator
from insight.agents.report_agent import ReportAgent
from insight.config import get_settings
from insight.eval.agent_eval import evaluate_agent, summarize
from insight.eval.judge import Judge
from insight.tools.code_exec import DockerCodeExecutor
from insight.tools.db import Database
from insight.tools.llm import get_chat_client


def main() -> None:
    settings = get_settings()
    client = get_chat_client(settings)
    model = settings.chat_model
    db = Database(settings.db_path)
    executor = DockerCodeExecutor()

    def make_orchestrator() -> Orchestrator:
        return Orchestrator(
            client=client,
            model=model,
            tools=[
                make_sql_tool(client, model, db),
                make_analyst_tool(client, model, executor),
            ],
            critic=CriticAgent(client, model),
            report=ReportAgent(client, model),
        )

    judge = Judge(client, model)
    results = evaluate_agent(make_orchestrator, judge)

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
