"""下载 Spider dev(validation) 的一个【偏难】子集到 data/spider/，供 eval 使用。

难度用 gold SQL 的复杂度信号粗估（JOIN/GROUP BY/HAVING/嵌套/集合运算/多条件…），
按库分层、每库取最难的若干题，凑成跨域且有挑战性的子集。可重复运行。
注：这是透明的难度【代理】，不等于 Spider 官方 hardness。
"""

import json
from collections import defaultdict

from huggingface_hub import hf_hub_download

from insight.paths import DATA_DIR

REPO = "prem-research/spider"
SPIDER_DIR = DATA_DIR / "spider"
PER_DB = 5  # 每个库取最难的 5 题（× 20 库 ≈ 100 题）


def hardness(gold_sql: str) -> int:
    """粗略难度分：统计 gold SQL 的复杂度信号，越高越难。"""
    s = f" {gold_sql.lower()} "
    score = 0
    score += s.count(" join ")
    score += s.count(" group by ")
    score += s.count(" having ")
    score += s.count(" order by ")
    score += s.count(" union ") + s.count(" intersect ") + s.count(" except ")
    score += max(0, s.count("select") - 1)  # 嵌套子查询（多于 1 个 select）
    score += s.count(" and ") + s.count(" or ")  # 多条件
    return score


def main() -> None:
    SPIDER_DIR.mkdir(parents=True, exist_ok=True)

    val_path = hf_hub_download(
        repo_id=REPO,
        repo_type="dataset",
        filename="validation.json",
        local_dir=SPIDER_DIR,
    )
    with open(val_path, encoding="utf-8") as f:
        examples = json.load(f)

    # 按库分组，每库取最难的 PER_DB 题（跨全部 20 个 dev 库）
    by_db: dict[str, list] = defaultdict(list)
    for ex in examples:
        by_db[ex["db_id"]].append(ex)

    subset = []
    for exs in by_db.values():
        exs_sorted = sorted(exs, key=lambda e: hardness(e["query"]), reverse=True)
        subset.extend(exs_sorted[:PER_DB])

    # 下子集涉及到的数据库 sqlite 文件
    db_ids = sorted({ex["db_id"] for ex in subset})
    for db_id in db_ids:
        hf_hub_download(
            repo_id=REPO,
            repo_type="dataset",
            filename=f"database/{db_id}/{db_id}.sqlite",
            local_dir=SPIDER_DIR,
        )

    subset_path = SPIDER_DIR / "dev_subset.json"
    subset_path.write_text(
        json.dumps(subset, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    avg_hard = sum(hardness(ex["query"]) for ex in subset) / len(subset)
    print(
        f"✅ 子集：{len(subset)} 题，跨 {len(db_ids)} 个库，平均难度分 {avg_hard:.1f}"
    )
    print(f"   → {subset_path}")


if __name__ == "__main__":
    main()
