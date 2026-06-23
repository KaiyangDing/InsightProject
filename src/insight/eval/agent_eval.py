"""多智能体端到端评测：跑编排器答一组问题，用 LLM-as-judge 给报告打分、聚合。"""

from insight.eval.judge import Judge

EVAL_QUESTIONS = [
    "哪个品类的总销售额最高？给出金额。",
    "各地区分别有多少客户？",
    "各品类销售额占总销售额的百分比是多少？",
    "销售额最低的品类是哪个？",
    "哪个客户下的订单数最多？",
]


def evaluate_agent(make_orchestrator, judge: Judge, questions=None) -> list[dict]:
    """每题：跑一个全新编排器 → 拿报告+证据 → judge 打分。返回逐题结果。"""
    questions = questions if questions is not None else EVAL_QUESTIONS
    results = []
    for q in questions:
        orch = make_orchestrator()  # 每题一个全新编排器 = fresh workspace，互不污染
        result = orch.run(q)
        j = judge.judge(q, result.evidence, result.answer)
        results.append(
            {
                "question": q,
                "report": result.answer,
                "faithfulness": j.faithfulness,
                "relevance": j.relevance,
                "steps": result.steps,
                "reviews": result.reviews,
            }
        )
    return results


def summarize(results: list[dict]) -> dict:
    """聚合：只统计有效评分（>0），算 faithfulness/relevance 均值。"""
    valid = [r for r in results if r["faithfulness"] > 0 and r["relevance"] > 0]
    n = len(valid)
    if n == 0:
        return {"n": 0, "avg_faithfulness": 0.0, "avg_relevance": 0.0}
    return {
        "n": n,
        "avg_faithfulness": sum(r["faithfulness"] for r in valid) / n,
        "avg_relevance": sum(r["relevance"] for r in valid) / n,
    }


# TRAP_QUESTIONS = [
#     "列出每个客户的邮箱地址和总消费额。",  # 库里没有邮箱字段
#     "每个客户的手机号和下单次数分别是多少？",  # 没有手机号字段
#     "VIP 客户的平均消费金额是多少？",  # 没有 VIP 这个概念/字段
#     "为什么数码品类的销售额最近在下降？",  # 假前提：没有"下降"的依据
#     "预测下个月各品类的销售额。",  # 超出数据、无依据
# ]

TRAP_QUESTIONS = [
    # "每个客户的手机号和下单次数分别是多少？",  # 没有手机号字段
    "VIP 客户的平均消费金额是多少？",  # 没有 VIP 这个概念/字段
]


def compare(results_a: list[dict], results_b: list[dict]) -> dict:
    """对比两组评测结果的均分（A - B 的 delta）。"""
    sa, sb = summarize(results_a), summarize(results_b)
    return {
        "a": sa,
        "b": sb,
        "delta_faithfulness": sa["avg_faithfulness"] - sb["avg_faithfulness"],
        "delta_relevance": sa["avg_relevance"] - sb["avg_relevance"],
    }
