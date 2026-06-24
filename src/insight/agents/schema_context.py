"""Schema 上下文层：把裸 DDL 增强成"带业务说明 + 口径提示"的 schema，喂给 text2sql。

为什么需要：模型光看 DDL 不知道"销售额=order_items.price""客户要用 unique_id""品类是葡语"
这些业务口径——把它们显式注入，真实数据上的 SQL 准确率明显提升，也根治"瞎编口径"。
（生产里这层通常是维护的语义层/指标库；这里先用常量起步。）
"""


def build_schema_context(
    schema_ddl: str, table_notes: dict[str, str], global_hints: str
) -> str:
    """裸 DDL + 表说明 + 业务口径 → 增强版 schema 上下文。"""
    notes = "\n".join(f"- {t}: {desc}" for t, desc in table_notes.items())
    return f"{schema_ddl}\n\n【表说明】\n{notes}\n\n【关键业务口径】\n{global_hints}"


OLIST_TABLE_NOTES = {
    "orders": "订单主表，一行一单。customer_id 是'每单一个'的临时 id；order_status 如 delivered/shipped/canceled。",
    "order_items": "订单行（一单可多行）。商品售价在 price、运费在 freight_value；销售额按 price 汇总。",
    "order_payments": "支付记录。payment_value 是实付额(含运费/分期)，payment_type 如 credit_card/boleto/voucher。",
    "order_reviews": "评价。review_score 为 1-5 分；评论文本是葡萄牙语。",
    "products": "产品。product_category_name 是【葡萄牙语】品类名；列名 product_name_lenght/product_description_lenght 为数据集原始拼写。",
    "customers": "买家。customer_unique_id 才是真实的人(customer_id 每单一换)；州在 customer_state(如 SP/RJ)。",
    "sellers": "卖家。",
    "geolocation": "邮编→经纬度/城市映射(约百万行，按 zip_code_prefix 关联买家/卖家)。",
    "product_category_translation": "品类名 葡萄牙语→英文 对照表(如 beleza_saude→health_beauty)。",
}

OLIST_HINTS = """- 销售额/营收 = SUM(order_items.price)（products 表没有价格字段）。
- "客户/买家"用 customers.customer_unique_id 计数（orders.customer_id 每单一个，不能用来数人/算复购）。
- 凡涉及品类，【务必】join product_category_translation 输出英文名 product_category_name_english，不要直接用葡语原值 product_category_name。
- 列名注意拼写：product_name_lenght、product_description_lenght（数据集原始拼写，别写成 length）。
- 金额单位是巴西雷亚尔（R$）；时间字段是时间戳字符串。
- "已完成订单"一般指 order_status = 'delivered'。"""


def olist_schema_context(schema_ddl: str) -> str:
    """Olist 专用：把 db 的裸 DDL 增强成带 Olist 口径的上下文。"""
    return build_schema_context(schema_ddl, OLIST_TABLE_NOTES, OLIST_HINTS)


def build_overview(table_notes: dict[str, str], global_hints: str) -> str:
    """精简数据库概览：表说明 + 业务口径（不含完整 DDL），给编排器规划/路由用。"""
    notes = "\n".join(f"- {t}: {desc}" for t, desc in table_notes.items())
    return f"【数据库概览（有哪些表）】\n{notes}\n\n【关键业务口径】\n{global_hints}"


def olist_overview() -> str:
    return build_overview(OLIST_TABLE_NOTES, OLIST_HINTS)
