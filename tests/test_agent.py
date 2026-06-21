"""确定性测试 Text2SQLAgent 的自我纠错循环——用假 LLM，不调真实模型。"""

from types import SimpleNamespace

from insight.text2sql_agent import Text2SQLAgent


class FakeLLMClient:
    """假的 OpenAI 客户端：按预设脚本依次返回内容。"""

    def __init__(self, scripted_replies: list[str]):
        self._replies = list(scripted_replies)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs) -> SimpleNamespace:
        content = self._replies.pop(0)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )


def test_self_correction_recovers(sample_db):
    """第 1 次给坏 SQL → 报错喂回 → 第 2 次给好 SQL → 成功。"""
    bad_sql = "SELECT email FROM customers"
    good_sql = "SELECT region, COUNT(*) FROM customers GROUP BY region"
    agent = Text2SQLAgent(FakeLLMClient([bad_sql, good_sql]), "fake-model", sample_db)

    result = agent.run("各地区有多少客户？")

    assert result.success
    assert result.attempts == 2
    assert result.output == good_sql
    _, rows = result.result
    assert ("华东", 2) in rows


def test_gives_up_after_budget(sample_db):
    """连续 3 次坏 SQL，预算耗尽后返回 success=False（不再抛异常）。"""
    bad_sql = "SELECT email FROM customers"
    agent = Text2SQLAgent(
        FakeLLMClient([bad_sql, bad_sql, bad_sql]),
        "fake-model",
        sample_db,
        max_attempts=3,
    )

    result = agent.run("随便问")

    assert not result.success
    assert result.attempts == 3
