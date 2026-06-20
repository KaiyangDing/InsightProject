"""下载 Spider dev(validation) 的一个小子集到 data/spider/，供 eval 使用。

为省时省钱，只下子集涉及到的数据库文件（不拉全量）。可重复运行。
"""

import json
from collections import defaultdict

from huggingface_hub import hf_hub_download

from insight.db import Database
from insight.paths import DATA_DIR

REPO = "prem-research/spider"
SPIDER_DIR = DATA_DIR / "spider"
SUBSET_SIZE = 50  # 先取 50 题做基线
MAX_PER_DB = 10  # 每个库最多 10 题，保证跨库分布


def main() -> None:
    SPIDER_DIR.mkdir(parents=True, exist_ok=True)

    # 1) 下 dev(validation) 题目集（含 db_id / question / query[标准SQL]）
    val_path = hf_hub_download(
        repo_id=REPO,
        repo_type="dataset",
        filename="validation.json",
        local_dir=SPIDER_DIR,
    )
    with open(val_path, encoding="utf-8") as f:
        examples = json.load(f)

    # 2) 跨库分层抽样，凑一个子集
    per_db: dict[str, int] = defaultdict(int)
    subset = []
    for ex in examples:
        if per_db[ex["db_id"]] >= MAX_PER_DB:
            continue
        subset.append(ex)
        per_db[ex["db_id"]] += 1
        if len(subset) >= SUBSET_SIZE:
            break

    # 3) 下子集用到的数据库 sqlite 文件
    db_ids = sorted({ex["db_id"] for ex in subset})
    for db_id in db_ids:
        hf_hub_download(
            repo_id=REPO,
            repo_type="dataset",
            filename=f"database/{db_id}/{db_id}.sqlite",
            local_dir=SPIDER_DIR,
        )

    # 4) 存下本次子集，供下一步 eval 读取
    subset_path = SPIDER_DIR / "dev_subset.json"
    subset_path.write_text(
        json.dumps(subset, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✅ 下载完成：{len(subset)} 题，跨 {len(db_ids)} 个数据库")
    print(f"   子集 → {subset_path}")

    # 5) 冒烟：确认我们的 Database 能直接读 Spider 的库
    first = subset[0]
    db_file = SPIDER_DIR / "database" / first["db_id"] / f"{first['db_id']}.sqlite"
    db = Database(str(db_file))
    print(
        f"   冒烟（{first['db_id']}）：schema {len(db.get_schema_text())} 字符，可读 ✅"
    )


if __name__ == "__main__":
    main()
