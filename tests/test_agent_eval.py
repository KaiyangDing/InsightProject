"""测试多智能体评测的 runner 逻辑（假编排器 + 假 judge，不调真模型）。"""

from types import SimpleNamespace

from insight.eval.agent_eval import evaluate_agent, summarize
from insight.eval.judge import Judgment


class FakeOrch:
    def __init__(self, answer, evidence):
        self._answer = answer
        self._evidence = evidence

    def run(self, question):
        return SimpleNamespace(
            answer=self._answer, evidence=self._evidence, steps=2, reviews=1
        )


class FakeJudge:
    def __init__(self, judgments):
        self._judgments = list(judgments)
        self.seen = []

    def judge(self, question, evidence, report):
        self.seen.append((question, evidence, report))
        return self._judgments.pop(0)


def test_evaluate_agent_scores_each_question():
    judge = FakeJudge([Judgment(5, 4, ""), Judgment(3, 5, "")])
    results = evaluate_agent(
        lambda: FakeOrch("报告", "证据"), judge, questions=["q1", "q2"]
    )
    assert len(results) == 2
    assert results[0]["faithfulness"] == 5 and results[0]["relevance"] == 4
    assert judge.seen[0] == ("q1", "证据", "报告")  # judge 拿到 (问题, 证据, 报告)


def test_summarize_averages_valid_only():
    results = [
        {"faithfulness": 5, "relevance": 5},
        {"faithfulness": 3, "relevance": 1},
        {"faithfulness": 0, "relevance": 0},  # 无效评分，剔除
    ]
    s = summarize(results)
    assert s["n"] == 2
    assert s["avg_faithfulness"] == 4.0
    assert s["avg_relevance"] == 3.0


def test_compare_computes_delta():
    from insight.eval.agent_eval import compare

    a = [{"faithfulness": 5, "relevance": 5}]
    b = [{"faithfulness": 3, "relevance": 4}]
    c = compare(a, b)
    assert c["delta_faithfulness"] == 2.0
    assert c["delta_relevance"] == 1.0
