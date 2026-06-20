"""text2SQL：把自然语言问题 + 库 schema 交给 LLM，生成一条可执行的 SQLite SQL。

本模块只负责"生成 SQL"，不负责执行（执行在 db.Database，职责分离）。
"""

import re

from openai import OpenAI

SYSTEM_PROMPT = """你是一名严谨的数据分析师，精通 SQLite。
根据给定的数据库 schema，把用户的问题转换成一条 SQLite 查询语句。

要求：
- 只使用 schema 中出现的表和字段，不要臆造。
- 只允许 SELECT（只读）。
- 直接输出 SQL 本身，不要解释、不要 markdown 代码块。
"""

USER_TEMPLATE = """数据库 schema：
{schema}

问题：{question}

请输出对应的 SQLite 查询。"""


def generate_sql(client: OpenAI, model: str, question: str, schema: str) -> str:
    """调用 LLM 生成 SQL。temperature=0 追求确定性与可复现。"""
    resp = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": USER_TEMPLATE.format(schema=schema, question=question),
            },
        ],
    )
    raw = resp.choices[0].message.content or ""
    return _extract_sql(raw)


def _extract_sql(text: str) -> str:
    """从模型输出里提取干净 SQL：剥掉可能的 ```sql 代码块包裹。"""
    text = text.strip()
    fence = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    return text.strip().rstrip(";").strip()
