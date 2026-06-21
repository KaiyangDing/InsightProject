"""pandas 分析（带自我纠错）：LLM 生成 pandas 代码 → 沙箱执行 → 报错则把 traceback
喂回模型改了重试（与 SQL 自我纠错同构）。

数据进沙箱（关键）：沙箱读不到主机数据，把结果序列化成 JSON 随代码注入，
代码开头还原成 DataFrame `df`。
"""

import json
import re
from dataclasses import dataclass

from langfuse import observe
from openai import OpenAI

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


@dataclass
class AnalysisResult:
    code: str  # 最终/最后一次的 pandas 代码
    success: bool
    attempts: int  # 一共试了几次（含首次）
    stdout: str = ""  # 成功时的输出
    error: str = ""  # 失败时的报错


def build_analysis_code(columns: list[str], rows: list[tuple], pandas_code: str) -> str:
    """把"数据还原 preamble" + pandas 代码拼成可在沙箱里跑的完整脚本。"""
    data = json.dumps({"columns": columns, "rows": rows})
    return _DATA_PREAMBLE.format(data=data) + "\n" + pandas_code


def _extract_code(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    return text.strip()


def build_pandas_messages(
    question: str, columns: list[str], rows: list[tuple]
) -> list[dict]:
    return [
        {"role": "system", "content": PANDAS_SYSTEM},
        {
            "role": "user",
            "content": PANDAS_USER.format(
                columns=columns, sample=rows[:3], question=question
            ),
        },
    ]


def request_pandas_code(client: OpenAI, model: str, messages: list[dict]) -> str:
    resp = client.chat.completions.create(model=model, temperature=0, messages=messages)
    return _extract_code(resp.choices[0].message.content or "")


@observe(name="pandas-analysis")
def run_pandas_analysis(
    client: OpenAI,
    model: str,
    executor,
    question: str,
    columns: list[str],
    rows: list[tuple],
    max_attempts: int = 3,
) -> AnalysisResult:
    """生成 pandas 代码 → 沙箱执行 → 报错则喂回 traceback 改了重试。"""
    messages = build_pandas_messages(question, columns, rows)
    code = ""
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        code = request_pandas_code(client, model, messages)
        result = executor.run(build_analysis_code(columns, rows, code))
        if result.success:
            return AnalysisResult(code, True, attempt, stdout=result.stdout)
        # 报错 → 把代码 + traceback 喂回，让模型改
        last_error = result.error
        messages.append({"role": "assistant", "content": code})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"上面的代码执行报错：\n{result.error}\n"
                    f"请修正后重新输出 pandas 代码（只输出代码）。"
                ),
            }
        )
    return AnalysisResult(code, False, max_attempts, error=last_error)
