"""测试 pandas 分析：数据注入（build_analysis_code）+ 自我纠错（CodeAnalysisAgent）。"""

from types import SimpleNamespace

from insight.analysis import build_analysis_code
from insight.analysis_agent import CodeAnalysisAgent
from insight.code_exec import CodeExecutor


class FakeLLMClient:
    def __init__(self, replies):
        self._replies = list(replies)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=self._replies.pop(0)))
            ]
        )


def test_data_injected_and_computed():
    full = build_analysis_code(
        ["region", "total"],
        [("华东", 100), ("华北", 50)],
        "print(int(df['total'].sum()))",
    )
    r = CodeExecutor().run(full)
    assert r.success, r.error
    assert "150" in r.stdout


def test_chinese_data_round_trips():
    full = build_analysis_code(
        ["region"], [("华东",), ("华北",)], "print('华东' in df['region'].tolist())"
    )
    r = CodeExecutor().run(full)
    assert r.success, r.error
    assert "True" in r.stdout


def test_self_correction_recovers_from_bad_code():
    """第 1 次坏代码 → traceback 喂回 → 第 2 次好代码 → 成功。"""
    bad = "print(df['nonexistent'])"  # KeyError
    good = "print(int(df['total'].sum()))"
    agent = CodeAnalysisAgent(
        FakeLLMClient([bad, good]),
        "fake-model",
        CodeExecutor(),
        ["total"],
        [(100,), (50,)],
    )
    result = agent.run("求 total 之和")
    assert result.success
    assert result.attempts == 2
    assert "150" in result.result  # 成功时 result.result = stdout
