"""Olist EX 评测：手写 gold SQL，比对 agent 生成 SQL 的执行结果集（列序/行序无关）。"""

from insight.errors import SQLExecutionError
from insight.eval.evaluation import same_result

OLIST_EVAL = [
    {
        "cat": "计数",
        "q": "Olist 一共有多少笔订单？",
        "gold": "SELECT COUNT(*) FROM orders",
    },
    {"cat": "计数", "q": "有多少个卖家？", "gold": "SELECT COUNT(*) FROM sellers"},
    {
        "cat": "分组",
        "q": "每种订单状态各有多少订单？",
        "gold": "SELECT order_status, COUNT(*) FROM orders GROUP BY order_status",
    },
    {
        "cat": "去重",
        "q": "有多少种不同的支付方式？",
        "gold": "SELECT COUNT(DISTINCT payment_type) FROM order_payments",
    },
    {
        "cat": "💥销售额",
        "q": "Olist 的总销售额是多少？",
        "gold": "SELECT SUM(price) FROM order_items",
    },
    {
        "cat": "💥销售额+翻译",
        "q": "销售额最高的 5 个产品品类是哪些（用英文品类名）？",
        "gold": "SELECT t.product_category_name_english FROM order_items oi JOIN products p ON oi.product_id=p.product_id JOIN product_category_translation t ON p.product_category_name=t.product_category_name GROUP BY t.product_category_name_english ORDER BY SUM(oi.price) DESC LIMIT 5",
    },
    {
        "cat": "💥运费",
        "q": "总运费是多少？",
        "gold": "SELECT SUM(freight_value) FROM order_items",
    },
    {
        "cat": "💥客户去重",
        "q": "Olist 上一共有多少个客户？",
        "gold": "SELECT COUNT(DISTINCT customer_unique_id) FROM customers",
    },
    {
        "cat": "💥客户去重",
        "q": "下单次数达到 7 次及以上的客户有几个？",
        "gold": "SELECT COUNT(*) FROM (SELECT c.customer_unique_id FROM orders o JOIN customers c ON o.customer_id=c.customer_id GROUP BY c.customer_unique_id HAVING COUNT(*) >= 7)",
    },
    {
        "cat": "地理",
        "q": "客户记录最多的 5 个州是哪些？",
        "gold": "SELECT customer_state FROM customers GROUP BY customer_state ORDER BY COUNT(*) DESC LIMIT 5",
    },
    {
        "cat": "评价",
        "q": "平均评价分数是多少？",
        "gold": "SELECT AVG(review_score) FROM order_reviews",
    },
    {
        "cat": "评价",
        "q": "各评价分数(1-5)各有多少条？",
        "gold": "SELECT review_score, COUNT(*) FROM order_reviews GROUP BY review_score",
    },
    {
        "cat": "评价",
        "q": "有多少条 5 分评价？",
        "gold": "SELECT COUNT(*) FROM order_reviews WHERE review_score=5",
    },
    {
        "cat": "支付",
        "q": "每种支付方式有多少条支付记录？",
        "gold": "SELECT payment_type, COUNT(*) FROM order_payments GROUP BY payment_type",
    },
    {
        "cat": "支付",
        "q": "平均分期数是多少？",
        "gold": "SELECT AVG(payment_installments) FROM order_payments",
    },
    {
        "cat": "时间",
        "q": "2017 年有多少笔订单（按下单时间）？",
        "gold": "SELECT COUNT(*) FROM orders WHERE strftime('%Y', order_purchase_timestamp)='2017'",
    },
    {
        "cat": "时间",
        "q": "下单量最多的是哪个年-月？",
        "gold": "SELECT strftime('%Y-%m', order_purchase_timestamp) FROM orders GROUP BY 1 ORDER BY COUNT(*) DESC LIMIT 1",
    },
    {
        "cat": "状态",
        "q": "已交付(delivered)订单有多少笔？",
        "gold": "SELECT COUNT(*) FROM orders WHERE order_status='delivered'",
    },
    {
        "cat": "💥销售额+过滤",
        "q": "已交付订单的总销售额是多少？",
        "gold": "SELECT SUM(oi.price) FROM order_items oi JOIN orders o ON oi.order_id=o.order_id WHERE o.order_status='delivered'",
    },
    {
        "cat": "💥口径",
        "q": "在 order_items 表中，平均每个订单(order_id)有多少个订单项？",
        "gold": "SELECT CAST(COUNT(*) AS REAL)/COUNT(DISTINCT order_id) FROM order_items",
    },
]

# 开放/分析型问题：用于 LLM-as-judge 评报告质量（无 gold SQL）。
# 这类问题报告有发挥空间，judge 才能区分质量；也会触发 analyst 沙箱路径。
OLIST_JUDGE_QUESTIONS = [
    "Olist 的销售额在各个州（customer_state）是如何分布的？哪几个州最重要？",
    "Olist 的客户里回头客多吗？大部分是一次性客户还是会复购？",
    "Olist 的订单履约情况如何？大多数订单最终都成功交付了吗？",
    "从销售额和评价来看，哪些产品品类最值得重点关注？",
    "从评价分数看，Olist 整体的客户满意度怎么样？",
    "Olist 用户偏好哪种支付方式？分期付款常见吗？",
    "Olist 的订单量随时间（月份）是怎样变化的？有没有明显的高峰？",
]


def evaluate_ex(db, make_agent, cases=None) -> dict:
    """对每题：agent 生成并执行 SQL → 与 gold SQL 结果集比对(EX)。返回逐题 + 准确率。"""
    cases = cases if cases is not None else OLIST_EVAL
    results = []
    correct = 0
    for case in cases:
        try:
            _, gold_rows = db.run_query(case["gold"], max_rows=10000)
        except SQLExecutionError:
            gold_rows = None
        res = make_agent().run(case["q"])
        pred_rows = res.result[1] if res.success else None
        ok = bool(
            pred_rows is not None
            and gold_rows is not None
            and same_result(pred_rows, gold_rows)
        )
        correct += ok
        results.append(
            {"q": case["q"], "cat": case["cat"], "ok": ok, "sql": res.output}
        )
    return {"results": results, "ex": correct / len(cases), "n": len(cases)}
