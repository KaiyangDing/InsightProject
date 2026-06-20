"""在 Spider dev 子集上评测 text2SQL 的 Execution Accuracy(EX)。

基线版：对每题单次生成 SQL（不开自我纠错），在对应库执行，与 gold 结果集比对。
"""

import json

from insight.config import get_settings
from insight.db import Database
from insight.errors import SQLExecutionError
from insight.evaluation import same_result
from insight.llm import get_chat_client
from insight.paths import DATA_DIR
from insight.text2sql import build_messages, request_sql

SPIDER_DIR = DATA_DIR / "spider"
MAX_ROWS = 10000  # 评测放宽行数上限，避免截断导致比对失真


def db_path_for(db_id: str) -> str:
    return str(SPIDER_DIR / "database" / db_id / f"{db_id}.sqlite")


def main() -> None:
    subset = json.loads((SPIDER_DIR / "dev_subset.json").read_text(encoding="utf-8"))
    settings = get_settings()
    client = get_chat_client(settings)

    results = []
    correct = 0
    for i, ex in enumerate(subset, 1):
        db = Database(db_path_for(ex["db_id"]))
        schema = db.get_schema_text()

        # —— 基线：单次生成（之后想测纠错增益，把这行换成 agent 即可）——
        try:
            our_sql = request_sql(
                client, settings.chat_model, build_messages(ex["question"], schema)
            )
            _, our_rows = db.run_query(our_sql, max_rows=MAX_ROWS)
        except SQLExecutionError:
            our_sql, our_rows = None, None

        # 执行 gold SQL
        try:
            _, gold_rows = db.run_query(ex["query"], max_rows=MAX_ROWS)
        except SQLExecutionError:
            gold_rows = None

        ok = (
            our_rows is not None
            and gold_rows is not None
            and same_result(our_rows, gold_rows)
        )
        correct += ok
        results.append(
            {
                "db_id": ex["db_id"],
                "question": ex["question"],
                "gold_sql": ex["query"],
                "our_sql": our_sql,
                "correct": ok,
            }
        )
        print(
            f"[{i:>2}/{len(subset)}] {'✅' if ok else '❌'} {ex['db_id']}: {ex['question'][:48]}"
        )

    total = len(subset)
    print(
        f"\n===== EX 基线（单次生成）= {correct}/{total} = {correct / total:.1%} ====="
    )

    out = SPIDER_DIR / "eval_results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"明细 → {out}")

    print("\n----- 错例（最多 5 个）-----")
    shown = 0
    for r in results:
        if not r["correct"]:
            print(f"\nQ: {r['question']}\ngold: {r['gold_sql']}\nours: {r['our_sql']}")
            shown += 1
            if shown >= 5:
                break


if __name__ == "__main__":
    main()
