"""测试 schema 上下文层：拼装 + 关键口径注入 + agent 使用。"""

from insight.agents.schema_context import build_schema_context, olist_schema_context
from insight.agents.text2sql_agent import Text2SQLAgent


def test_build_combines_ddl_notes_hints():
    ctx = build_schema_context("CREATE TABLE t (a INT);", {"t": "测试表"}, "用 a 列。")
    assert "CREATE TABLE t" in ctx and "测试表" in ctx and "用 a 列" in ctx


def test_olist_context_carries_key_hints():
    ctx = olist_schema_context("DDL...")
    assert "customer_unique_id" in ctx  # 关键口径确实注入了
    assert "order_items.price" in ctx


def test_agent_uses_schema_context_when_provided(sample_db):
    agent = Text2SQLAgent(None, "m", sample_db, schema_context="MY_CONTEXT")
    msgs = agent.initial_messages("各地区客户数")
    assert any("MY_CONTEXT" in m["content"] for m in msgs)


def test_agent_falls_back_to_db_schema(sample_db):
    agent = Text2SQLAgent(None, "m", sample_db)  # 没给 context → 用 db 真实 schema
    msgs = agent.initial_messages("各地区客户数")
    assert any("customers" in m["content"] for m in msgs)
