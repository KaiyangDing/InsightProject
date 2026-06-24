"""Olist EX A/B：text2SQL 带 vs 不带 schema_context，比 EX + 打印两边失败的 SQL。"""

from insight.agents.schema_context import olist_schema_context
from insight.agents.text2sql_agent import Text2SQLAgent
from insight.config import get_settings
from insight.eval.olist_eval import OLIST_EVAL, evaluate_ex
from insight.tools.db import Database
from insight.tools.llm import get_chat_client


def main() -> None:
    settings = get_settings()
    client = get_chat_client(settings)
    model = settings.chat_model
    db = Database(settings.db_path)
    ctx = olist_schema_context(db.get_schema_text())

    no_ctx = evaluate_ex(db, lambda: Text2SQLAgent(client, model, db))
    with_ctx = evaluate_ex(
        db, lambda: Text2SQLAgent(client, model, db, schema_context=ctx)
    )

    print(f"不带 schema_context：EX = {no_ctx['ex']:.1%}  ({no_ctx['n']} 题)")
    print(f"带   schema_context：EX = {with_ctx['ex']:.1%}")
    print(f"Δ = {with_ctx['ex'] - no_ctx['ex']:+.1%}\n")

    print("逐题对照（✓对 ✗错）：")
    for a, b in zip(no_ctx["results"], with_ctx["results"]):
        mark = "  " if a["ok"] == b["ok"] else "←变化"
        print(
            f"  {a['cat']:14s} 不带[{'✓' if a['ok'] else '✗'}] 带[{'✓' if b['ok'] else '✗'}] {mark}  {a['q']}"
        )

    gold_map = {c["q"]: c["gold"] for c in OLIST_EVAL}
    for label, res in [
        ("不带 schema_context", no_ctx),
        ("带 schema_context", with_ctx),
    ]:
        print(f"\n=== {label} 失败的题（gold vs pred，判断真错 / 度量边界）===")
        for r in res["results"]:
            if not r["ok"]:
                print(f"\n● {r['q']}")
                print(f"  gold: {gold_map[r['q']]}")
                print(f"  pred: {r['sql']}")


if __name__ == "__main__":
    main()
