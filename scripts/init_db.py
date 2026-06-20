"""创建并填充示例电商数据库 data/insight.db（开发期一次性脚本）。

重复运行会先清空再重建，保证可复现。这是项目里唯一对库写入的地方。
"""

import sqlite3

from insight.paths import DATA_DIR

DB_PATH = DATA_DIR / "insight.db"

SCHEMA = """
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    city        TEXT,
    region      TEXT,               -- 华东/华北/华南 ...
    signup_date TEXT
);

CREATE TABLE products (
    id       INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    category TEXT,
    price    REAL NOT NULL
);

CREATE TABLE orders (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    order_date  TEXT NOT NULL,
    status      TEXT NOT NULL        -- paid/refunded ...
);

CREATE TABLE order_items (
    id         INTEGER PRIMARY KEY,
    order_id   INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    quantity   INTEGER NOT NULL,
    unit_price REAL NOT NULL
);
"""

CUSTOMERS = [
    (1, "张伟", "上海", "华东", "2024-01-05"),
    (2, "李娜", "杭州", "华东", "2024-02-11"),
    (3, "王芳", "北京", "华北", "2024-01-20"),
    (4, "刘洋", "深圳", "华南", "2024-03-02"),
    (5, "陈静", "广州", "华南", "2024-02-28"),
    (6, "赵磊", "苏州", "华东", "2024-03-15"),
]

PRODUCTS = [
    (1, "无线耳机", "数码", 299.0),
    (2, "机械键盘", "数码", 459.0),
    (3, "保温杯", "家居", 89.0),
    (4, "瑜伽垫", "运动", 129.0),
    (5, "蓝牙音箱", "数码", 199.0),
    (6, "羽绒被", "家居", 599.0),
]

ORDERS = [
    (1, 1, "2024-04-03", "paid"),
    (2, 1, "2024-05-12", "paid"),
    (3, 2, "2024-04-18", "paid"),
    (4, 3, "2024-04-21", "refunded"),
    (5, 4, "2024-05-01", "paid"),
    (6, 5, "2024-05-09", "paid"),
    (7, 2, "2024-05-20", "paid"),
    (8, 6, "2024-05-25", "paid"),
]

ORDER_ITEMS = [
    # id, order_id, product_id, quantity, unit_price
    (1, 1, 1, 1, 299.0),
    (2, 1, 3, 2, 89.0),
    (3, 2, 2, 1, 459.0),
    (4, 3, 5, 1, 199.0),
    (5, 4, 6, 1, 599.0),
    (6, 5, 4, 2, 129.0),
    (7, 5, 1, 1, 299.0),
    (8, 6, 3, 1, 89.0),
    (9, 7, 2, 1, 459.0),
    (10, 8, 5, 2, 199.0),
]


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", CUSTOMERS)
        conn.executemany("INSERT INTO products VALUES (?,?,?,?)", PRODUCTS)
        conn.executemany("INSERT INTO orders VALUES (?,?,?,?)", ORDERS)
        conn.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", ORDER_ITEMS)
        conn.commit()
        for table in ("customers", "products", "orders", "order_items"):
            n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table:12s}: {n} 行")
    print(f"✅ 示例库已生成：{DB_PATH}")


if __name__ == "__main__":
    main()
