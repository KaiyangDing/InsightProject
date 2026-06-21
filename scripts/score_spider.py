"""第 2 步：读取冻结的预测，执行并打分（不调模型，可反复跑）。

用法：
    uv run scripts/score_spider.py                        # 打分 predictions.json
    uv run scripts/score_spider.py predictions_agent.json # 打分指定文件
"""

import json
import sys

from insight.tools.db import Database
from insight.errors import SQLExecutionError
from insight.eval.evaluation import same_result
from insight.paths import DATA_DIR

SPIDER_DIR = DATA_DIR / "spider"
MAX_ROWS = 10000


def db_path_for(db_id: str) -> str:
    return str(SPIDER_DIR / "database" / db_id / f"{db_id}.sqlite")


def main() -> None:
    preds_file = sys.argv[1] if len(sys.argv) > 1 else "predictions.json"
    preds = json.loads((SPIDER_DIR / preds_file).read_text(encoding="utf-8"))

    results = []
    correct = 0
    for p in preds:
        db = Database(db_path_for(p["db_id"]))

        our_rows = None
        if p["our_sql"]:
            try:
                _, our_rows = db.run_query(p["our_sql"], max_rows=MAX_ROWS)
            except SQLExecutionError:
                our_rows = None

        try:
            _, gold_rows = db.run_query(p["gold_sql"], max_rows=MAX_ROWS)
        except SQLExecutionError:
            gold_rows = None

        ok = (
            our_rows is not None
            and gold_rows is not None
            and same_result(our_rows, gold_rows)
        )
        correct += ok
        results.append({**p, "correct": ok})

    total = len(preds)
    print(f"===== [{preds_file}] EX = {correct}/{total} = {correct / total:.1%} =====")

    out = SPIDER_DIR / f"scored_{preds_file}"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"明细 → {out}")


if __name__ == "__main__":
    main()
