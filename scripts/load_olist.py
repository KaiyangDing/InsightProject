"""把 Olist 巴西电商 CSV 加载进 data/olist.db（一次性 ETL）。

数据来源：Kaggle "olistbr/brazilian-ecommerce"。先把解压的 CSV 放进 data/olist_csv/。
用法：uv run scripts/load_olist.py
"""

import sqlite3

import pandas as pd

from insight.paths import DATA_DIR

CSV_DIR = DATA_DIR / "olist_csv"
DB_PATH = DATA_DIR / "olist.db"

# CSV 文件名 → 干净的表名
TABLES = {
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "olist_products_dataset.csv": "products",
    "olist_customers_dataset.csv": "customers",
    "olist_sellers_dataset.csv": "sellers",
    "olist_geolocation_dataset.csv": "geolocation",
    "product_category_name_translation.csv": "product_category_translation",
}


def main() -> None:
    DB_PATH.unlink(missing_ok=True)  # 重建保证可复现
    with sqlite3.connect(DB_PATH) as conn:
        for csv_name, table in TABLES.items():
            path = CSV_DIR / csv_name
            if not path.exists():
                print(f"⚠️ 缺文件，跳过：{path}")
                continue
            df = pd.read_csv(path)
            df.to_sql(table, conn, if_exists="replace", index=False)
            print(f"  {table:30s}: {len(df):>7} 行")
    print(f"✅ Olist 库已生成：{DB_PATH}")


if __name__ == "__main__":
    main()
