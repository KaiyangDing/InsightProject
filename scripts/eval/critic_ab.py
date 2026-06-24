"""Critic 有效性 A/B：同一组陷阱题，对比挂 Critic vs 不挂 Critic 的忠实性评分。

用法：uv run scripts/eval/critic_ab.py
"""

from langfuse import get_client

from insight.agents.agent_tools import make_analyst_tool, make_sql_tool
from insight.agents.critic_agent import CriticAgent
from insight.agents.orchestrator import Orchestrator
from insight.agents.report_agent import ReportAgent
from insight.agents.schema_context import olist_overview, olist_schema_context
from insight.config import get_settings
from insight.eval.agent_eval import TRAP_QUESTIONS, compare, evaluate_agent
from insight.eval.judge import Judge
from insight.tools.code_exec import DockerCodeExecutor
from insight.tools.db import Database
from insight.tools.llm import get_chat_client


def make_factory(client, model, db, executor, with_critic: bool):
    schema_ctx = olist_schema_context(db.get_schema_text())

    def _factory():
        return Orchestrator(
            client=client,
            model=model,
            tools=[
                make_sql_tool(client, model, db, schema_context=schema_ctx),
                make_analyst_tool(client, model, executor),
            ],
            critic=CriticAgent(client, model) if with_critic else None,
            report=ReportAgent(client, model),
            schema_overview=olist_overview(),
        )

    return _factory


def main() -> None:
    settings = get_settings()
    client = get_chat_client(settings)
    model = settings.chat_model
    db = Database(settings.db_path)
    executor = DockerCodeExecutor()
    judge = Judge(client, model)

    with_results = evaluate_agent(
        make_factory(client, model, db, executor, True), judge, TRAP_QUESTIONS
    )
    without_results = evaluate_agent(
        make_factory(client, model, db, executor, False), judge, TRAP_QUESTIONS
    )

    c = compare(with_results, without_results)
    print(
        f"挂 Critic   ：忠实 {c['a']['avg_faithfulness']:.2f} / 相关 {c['a']['avg_relevance']:.2f}"
    )
    print(
        f"不挂 Critic ：忠实 {c['b']['avg_faithfulness']:.2f} / 相关 {c['b']['avg_relevance']:.2f}"
    )
    print(f"Δ忠实性 = {c['delta_faithfulness']:+.2f}（>0 = Critic 提升了忠实性）")

    get_client().flush()


if __name__ == "__main__":
    main()
