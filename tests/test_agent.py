"""确定性测试 Text2SQLAgent 的自我纠错循环——用假 LLM，不调真实模型。"""

from types import SimpleNamespace

import pytest

from insight.agent import Text2SQLAgent
from insight.errors import SQLExecutionError


class FakeLLMClient:
    """假的 OpenAI 客户端：按预设脚本依次返回内容，模拟 client.chat.completions.create。"""

    def __init__(self, scripted_replies: list[str]):
        self._replies = list(scripted_replies)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs) -> SimpleNamespace:
        content = self._replies.pop(0)  # 每调一次，吐下一条脚本
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


def test_self_correction_recovers(sample_db):
    """第 1 次给坏 SQL（email 列不存在）→ 报错喂回 → 第 2 次给好 SQL → 成功。"""
    bad_sql = "SELECT email FROM customers"
    good_sql = "SELECT region, COUNT(*) FROM customers GROUP BY region"
    agent = Text2SQLAgent(FakeLLMClient([bad_sql, good_sql]), "fake-model", sample_db)

    result = agent.run("各地区有多少客户？")

    assert result.attempts == 2  # 证明确实走了两轮（坏→好）
    assert result.sql == good_sql
    assert ("华东", 2) in result.rows


def test_gives_up_after_budget(sample_db):
    """连续 3 次都是坏 SQL，预算耗尽后应抛 SQLExecutionError。"""
    bad_sql = "SELECT email FROM customers"
    agent = Text2SQLAgent(
        FakeLLMClient([bad_sql, bad_sql, bad_sql]),
        "fake-model",
        sample_db,
        max_attempts=3,
    )

    with pytest.raises(SQLExecutionError):
        agent.run("随便问")
