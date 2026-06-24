"""pandas 代码生成 + 数据注入 + 图表回传（纯生成/工具，不含执行循环）。

数据进沙箱：SQL 结果序列化 JSON 随代码注入，代码开头还原成 df。
图表出沙箱：沙箱里 emit_chart() 把图存 PNG→base64 打印；主机 extract_chart() 解码。
"""

import base64
import json
import re

from openai import OpenAI

CHART_MARKER = "__CHART_PNG_BASE64__"

PANDAS_SYSTEM = """你是数据分析师，精通 pandas 和 matplotlib。
会给你一个已加载好的 pandas DataFrame `df` 和一个分析问题。
写 Python 代码回答它。

要求：
- 只用 df 和 pandas / matplotlib / 标准库；不要重新读数据、不要联网、不要读写文件。
- 文本结论用 print 输出。
- 若需要图表：用 matplotlib 画好后调用 `emit_chart()`（已为你提供，**不要** plt.show() 或自己存文件）。
- 直接输出代码本身，不要解释、不要 markdown。
"""

PANDAS_USER = """df 的列：{columns}
前几行示例：{sample}

问题：{question}

请写出代码（用 df，print 文本结论 / 需要时调 emit_chart()）。"""

_DATA_PREAMBLE = """import json
import pandas as pd

_payload = json.loads({data!r})
df = pd.DataFrame(_payload["rows"], columns=_payload["columns"])
"""

# 画图前设好中文字体（在沙箱里，画图代码运行之前执行；主机无 matplotlib 时静默跳过）
_FONT_SETUP = """
try:
    import matplotlib.pyplot as plt


    plt.style.use("seaborn-v0_8-darkgrid")  # seaborn 同款风格（matplotlib 内置）
    plt.rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei", "DejaVu Sans"]  # 风格之后再设字体，不被覆盖
    plt.rcParams["axes.unicode_minus"] = False
except (ImportError, OSError):
    pass
"""

_CHART_HELPER = f'''

def emit_chart(fig=None):
    """把 matplotlib 图存成 PNG→base64 打印（带 marker）；图片靠这条出沙箱。"""
    import base64
    import io

    import matplotlib.pyplot as plt

    buf = io.BytesIO()
    target = fig if fig is not None else plt.gcf()
    target.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    print("{CHART_MARKER}" + base64.b64encode(buf.getvalue()).decode())
'''


def build_analysis_code(columns: list[str], rows: list[tuple], pandas_code: str) -> str:
    """数据还原 preamble + 中文字体设置 + emit_chart 工具 + LLM 代码。"""
    data = json.dumps({"columns": columns, "rows": rows})
    return (
        _DATA_PREAMBLE.format(data=data)
        + _FONT_SETUP
        + _CHART_HELPER
        + "\n"
        + pandas_code
    )


def extract_chart(stdout: str) -> tuple[str, bytes | None]:
    """从 stdout 抽出图（base64 PNG）。返回 (去掉图行后的文本, png 字节或 None)。"""
    png = None
    text_lines = []
    for line in stdout.splitlines():
        if line.startswith(CHART_MARKER):
            png = base64.b64decode(line[len(CHART_MARKER) :])
        else:
            text_lines.append(line)
    return "\n".join(text_lines), png


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
