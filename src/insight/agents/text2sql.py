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
- 对 schema 中未定义的业务术语，不要编造具体数值阈值；优先查询可直接计算的基础数据，把"口径如何定"留给上层声明。
- 直接输出 SQL 本身，不要解释、不要 markdown 代码块。

注意以下高频易错点：
- "同时满足两个独立条件 / 既…又…（both A and B）" → 优先用 INTERSECT；
- "是 A 但不是 B / 没有…的" → 用 EXCEPT（集合差），而非简单的 != 或 NOT IN；
- "A 或 B 的并集" → 用 UNION；
- 注意 AND/OR 优先级，必要时加括号；
- 字面值（国家/语言/类别名等）的大小写要贴合数据中的实际写法。
"""

USER_TEMPLATE = """数据库 schema：
{schema}

问题：{question}

请输出对应的 SQLite 查询。"""

# few-shot 示例用一个【通用合成 schema】（非 Spider 测试题，避免泄题），只教模式。
FEW_SHOT_SCHEMA = """CREATE TABLE student (id INT, name TEXT, grade TEXT, gpa REAL);
CREATE TABLE membership (student_id INT, club TEXT);"""

FEW_SHOT: list[tuple[str, str]] = [
    (
        "Find the names of students who are in both the 'Chess' club and the 'Art' club.",
        "SELECT name FROM student JOIN membership ON student.id = membership.student_id "
        "WHERE club = 'Chess' INTERSECT SELECT name FROM student JOIN membership "
        "ON student.id = membership.student_id WHERE club = 'Art'",
    ),
    (
        "Find the names of students in the 'Chess' club but not in the 'Art' club.",
        "SELECT name FROM student JOIN membership ON student.id = membership.student_id "
        "WHERE club = 'Chess' EXCEPT SELECT name FROM student JOIN membership "
        "ON student.id = membership.student_id WHERE club = 'Art'",
    ),
    (
        "List the names of students who are seniors, or juniors with a GPA above 3.5.",
        "SELECT name FROM student WHERE grade = 'senior' "
        "UNION SELECT name FROM student WHERE grade = 'junior' AND gpa > 3.5",
    ),
]


def build_messages(question: str, schema: str) -> list[dict]:
    """system + 几个 few-shot 示例 + 真实问题。"""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for ex_q, ex_sql in FEW_SHOT:
        messages.append(
            {
                "role": "user",
                "content": USER_TEMPLATE.format(schema=FEW_SHOT_SCHEMA, question=ex_q),
            }
        )
        messages.append({"role": "assistant", "content": ex_sql})
    messages.append(
        {
            "role": "user",
            "content": USER_TEMPLATE.format(schema=schema, question=question),
        }
    )
    return messages


def request_sql(client: OpenAI, model: str, messages: list[dict]) -> str:
    """按给定消息历史请求一条 SQL（首轮和纠错轮都用它）。temperature=0 求确定性。"""
    resp = client.chat.completions.create(model=model, temperature=0, messages=messages)
    raw = resp.choices[0].message.content or ""
    return _extract_sql(raw)


def _extract_sql(text: str) -> str:
    """从模型输出里提取干净 SQL：剥掉可能的 ```sql 代码块包裹。"""
    text = text.strip()
    fence = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    return text.strip().rstrip(";").strip()
