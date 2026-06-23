"""测试 LLM-as-judge（用假裁判 LLM 吐 tool_calls，不调真模型）。"""

import json
from types import SimpleNamespace

from insight.eval.judge import Judge, Judgment


def _judgment_response(faithfulness, relevance, rationale) -> SimpleNamespace:
    args = json.dumps(
        {"faithfulness": faithfulness, "relevance": relevance, "rationale": rationale}
    )
    tc = SimpleNamespace(
        id="c1", function=SimpleNamespace(name="submit_judgment", arguments=args)
    )
    message = SimpleNamespace(content=None, tool_calls=[tc])
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeJudgeLLM:
    def __init__(self, response):
        self._response = response
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        return self._response


def test_judge_parses_scores():
    judge = Judge(FakeJudgeLLM(_judgment_response(5, 4, "切题且忠实")), "m")
    result = judge.judge("问题", "证据", "报告")
    assert isinstance(result, Judgment)
    assert result.faithfulness == 5
    assert result.relevance == 4
    assert "切题" in result.rationale


def test_judge_handles_missing_tool_call():
    """裁判没按要求调工具 → 返回哨兵 0 分，不崩。"""
    no_tc = SimpleNamespace(
        choices=[
            SimpleNamespace(message=SimpleNamespace(content="忘了调", tool_calls=None))
        ]
    )
    judge = Judge(FakeJudgeLLM(no_tc), "m")
    result = judge.judge("q", "e", "r")
    assert result.faithfulness == 0
    assert result.relevance == 0
