"""第 1 步：对 Spider 子集逐题生成 SQL，把预测冻结存盘（不打分、不执行）。

模型只跑这一次；之后改度量只需重新 score，不必再调模型。
"""

import json

from insight.config import get_settings
from insight.db import Database
from insight.llm import get_chat_client
from insight.paths import DATA_DIR
from insight.text2sql import build_messages, request_sql

SPIDER_DIR = DATA_DIR / "spider"


def db_path_for(db_id: str) -> str:
    return str(SPIDER_DIR / "database" / db_id / f"{db_id}.sqlite")


def main() -> None:
    subset = json.loads((SPIDER_DIR / "dev_subset.json").read_text(encoding="utf-8"))
    settings = get_settings()
    client = get_chat_client(settings)

    predictions = []
    for i, ex in enumerate(subset, 1):
        db = Database(db_path_for(ex["db_id"]))
        schema = db.get_schema_text()
        our_sql = request_sql(
            client, settings.chat_model, build_messages(ex["question"], schema)
        )
        predictions.append(
            {
                "db_id": ex["db_id"],
                "question": ex["question"],
                "gold_sql": ex["query"],
                "our_sql": our_sql,
            }
        )
        print(f"[{i:>3}/{len(subset)}] {ex['db_id']}: {ex['question'][:50]}")

    out = SPIDER_DIR / "predictions.json"
    out.write_text(
        json.dumps(predictions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n✅ 预测已冻结：{len(predictions)} 条 → {out}")


if __name__ == "__main__":
    main()
