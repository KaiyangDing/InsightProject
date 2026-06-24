"""测试 evaluate_ex 的打分逻辑（假 agent + sample_db）。"""

from types import SimpleNamespace

from insight.eval.olist_eval import evaluate_ex

GOLD = "SELECT region, COUNT(*) FROM customers GROUP BY region"


def _agent_returning(sql, db):
    cols, rows = db.run_query(sql)
    return SimpleNamespace(
        run=lambda q: SimpleNamespace(success=True, output=sql, result=(cols, rows))
    )


def test_ex_correct_when_results_match(sample_db):
    cases = [{"cat": "t", "q": "各地区客户数", "gold": GOLD}]
    out = evaluate_ex(sample_db, lambda: _agent_returning(GOLD, sample_db), cases)
    assert out["ex"] == 1.0


def test_ex_wrong_when_results_differ(sample_db):
    cases = [{"cat": "t", "q": "各地区客户数", "gold": GOLD}]
    bad = "SELECT region, COUNT(*) FROM customers WHERE region='华东' GROUP BY region"
    out = evaluate_ex(sample_db, lambda: _agent_returning(bad, sample_db), cases)
    assert out["ex"] == 0.0