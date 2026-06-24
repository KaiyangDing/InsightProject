"""Insight 的 HTTP API：把多智能体编排包成 REST 服务。

本地启动：uv run uvicorn api.main:app --reload  → 打开 http://localhost:8000/docs
"""

import base64
from functools import lru_cache

from fastapi import Depends, FastAPI
from pydantic import BaseModel

from insight.agents.agent_tools import CHART_KEY, make_analyst_tool, make_sql_tool
from insight.agents.critic_agent import CriticAgent
from insight.agents.orchestrator import Orchestrator
from insight.agents.report_agent import ReportAgent
from insight.agents.schema_context import olist_schema_context, olist_overview
from insight.config import get_settings
from insight.tools.code_exec import DockerCodeExecutor
from insight.tools.db import Database
from insight.tools.llm import get_chat_client

app = FastAPI(title="Insight · 自主数据分析 Agent")


@lru_cache
def _components():
    """重资源懒加载、只建一次（client/db/executor/schema 上下文）。"""
    settings = get_settings()
    client = get_chat_client(settings)
    db = Database(settings.db_path)
    return (
        client,
        settings.chat_model,
        db,
        DockerCodeExecutor(),
        olist_schema_context(db.get_schema_text()),
    )


def get_orchestrator() -> Orchestrator:
    """每请求构造一个全新编排器（干净 workspace）。测试里可 override 这个依赖。"""
    client, model, db, executor, schema_ctx = _components()
    return Orchestrator(
        client=client,
        model=model,
        tools=[
            make_sql_tool(client, model, db, schema_context=schema_ctx),
            make_analyst_tool(client, model, executor),
        ],
        critic=CriticAgent(client, model),
        report=ReportAgent(client, model),
        schema_overview=olist_overview(),
    )


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    steps: int
    reviews: int
    tool_calls: list
    chart_png_base64: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest, orch: Orchestrator = Depends(get_orchestrator)) -> AskResponse:
    result = orch.run(req.question)
    png = orch.workspace.get(CHART_KEY)
    return AskResponse(
        answer=result.answer,
        steps=result.steps,
        reviews=result.reviews,
        tool_calls=result.tool_calls,
        chart_png_base64=base64.b64encode(png).decode() if png else None,
    )
