"""Insight 网页 demo：输入问题 → 多智能体编排 → 展示报告/轨迹/图表。

启动：uv run streamlit run streamlit_app.py
（需 Docker 在跑 + 已 build insight-sandbox 镜像 + 配好 DASHSCOPE_API_KEY）
"""

import streamlit as st

from insight.agents.agent_tools import CHART_KEY, make_analyst_tool, make_sql_tool
from insight.agents.critic_agent import CriticAgent
from insight.agents.orchestrator import Orchestrator
from insight.agents.report_agent import ReportAgent
from insight.config import get_settings
from insight.tools.code_exec import DockerCodeExecutor
from insight.tools.db import Database
from insight.tools.llm import get_chat_client

EXAMPLES = [
    "把各品类的总销售额画成柱状图，并指出最高的品类。",
    "各地区分别有多少客户？",
    "各品类销售额占总销售额的百分比是多少？",
]


@st.cache_resource
def get_components():
    """重资源只建一次（client/db/executor），跨 rerun 复用。"""
    settings = get_settings()
    client = get_chat_client(settings)
    return client, settings.chat_model, Database(settings.db_path), DockerCodeExecutor()


def make_orchestrator() -> Orchestrator:
    client, model, db, executor = get_components()
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


st.set_page_config(page_title="Insight · 自主数据分析 Agent", page_icon="📊")
st.title("📊 Insight · 自主数据分析 Agent")
st.caption("自然语言提问 → 多智能体自主完成 取数 → 分析 → 审查 → 报告")

with st.sidebar:
    st.markdown("**说明**")
    st.markdown("- 模型：阿里云百炼 qwen-plus")
    st.markdown("- 分析/画图在 Docker 沙箱里执行")
    st.markdown("- 详细成本/链路见 Langfuse")

question = st.text_input("问数据库", placeholder="例如：哪个品类的总销售额最高？")
cols = st.columns(len(EXAMPLES))
for col, ex in zip(cols, EXAMPLES):
    if col.button(ex, use_container_width=True):
        question = ex

if question:
    try:
        with st.spinner("多智能体协作中（取数 → 分析 → 审查 → 报告）…"):
            orch = make_orchestrator()
            result = orch.run(question)
    except Exception as e:
        st.error(f"出错了：{e}")
        st.stop()

    st.subheader("📝 报告")
    st.markdown(result.answer)

    png = orch.workspace.get(CHART_KEY)
    if png:
        st.subheader("📈 图表")
        st.image(png)

    c1, c2 = st.columns(2)
    c1.metric("编排步数", result.steps)
    c2.metric("审查轮数", result.reviews)

    with st.expander("🧭 编排轨迹（自主调了哪些工具）"):
        if result.tool_calls:
            for i, call in enumerate(result.tool_calls, 1):
                st.write(f"{i}. `{call['name']}`({call['args']})")
        else:
            st.write("（未调用工具，直接作答）")

    with st.expander("🔍 证据（工具返回的真实数据）"):
        st.text(result.evidence or "（无）")