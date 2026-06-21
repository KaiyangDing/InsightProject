"""pandas 分析：把 SQL 结果交给 LLM 生成 pandas 代码，在沙箱里执行得到进阶结果。

数据怎么进沙箱（关键）：沙箱读不到主机数据，所以把结果序列化成 JSON 随代码注入，
代码开头还原成 DataFrame `df`。
"""

import json
import re

from openai import OpenAI

from insight.code_exec import ExecutionResult

PANDAS_SYSTEM = """你是数据分析师，精通 pandas。
会给你一个已加载好的 pandas DataFrame `df` 和一个分析问题。
写 Python(pandas) 代码回答它，并 print 出结果。

要求：
- 只用 df 和 pandas / 标准库；不要重新读数据、不要联网、不要读写文件。
- 直接输出代码本身，不要解释、不要 markdown。
- 必须 print 出最终答案。
"""

PANDAS_USER = """df 的列：{columns}
前几行示例：{sample}

问题：{question}

请写出 pandas 代码（用 df，print 出结果）。"""

_DATA_PREAMBLE = """import json
import pandas as pd

_payload = json.loads({data!r})
df = pd.DataFrame(_payload["rows"], columns=_payload["columns"])
"""


def build_analysis_code(columns: list[str], rows: list[tuple], pandas_code: str) -> str:
    """把"数据还原 preamble" + LLM 的 pandas 代码拼成可在沙箱里跑的完整脚本。"""
    data = json.dumps({"columns": columns, "rows": rows})
    return _DATA_PREAMBLE.format(data=data) + "\n" + pandas_code


def _extract_code(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    return text.strip()


def generate_pandas_code(
    client: OpenAI, model: str, question: str, columns: list[str], rows: list[tuple]
) -> str:
    """让 LLM 针对 df 写 pandas 代码。"""
    messages = [
        {"role": "system", "content": PANDAS_SYSTEM},
        {
            "role": "user",
            "content": PANDAS_USER.format(
                columns=columns, sample=rows[:3], question=question
            ),
        },
    ]
    resp = client.chat.completions.create(model=model, temperature=0, messages=messages)
    return _extract_code(resp.choices[0].message.content or "")


def run_pandas_analysis(
    client: OpenAI,
    model: str,
    executor,
    question: str,
    columns: list[str],
    rows: list[tuple],
) -> tuple[str, ExecutionResult]:
    """生成 pandas 代码 → 拼上数据 → 在 executor(沙箱) 里执行。返回 (代码, 结果)。"""
    pandas_code = generate_pandas_code(client, model, question, columns, rows)
    full_code = build_analysis_code(columns, rows, pandas_code)
    return pandas_code, executor.run(full_code)
