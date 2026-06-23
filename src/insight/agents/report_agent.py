"""ReportAgent：把编排过程收集到的证据合成一份结构化的最终报告。

只读"证据"（工具返回的真实数据/分析），不自己查库/算数——保证每个结论可溯源。
"""

from langfuse import observe
from openai import OpenAI

REPORT_SYSTEM = """你是一名数据分析报告撰写员。会给你：用户问题，以及"证据"（系统通过工具取到的真实数据与分析结果）。
基于证据写一份简洁的中文分析报告。

要求：
- 只用证据里出现的数据和结论，不要臆造、不要心算证据里没有的数字。
- 结构：① 直接结论（一两句回答用户问题）② 关键数据支撑（列出相关数字）③ 若证据提到已生成图表，注明"见图表" ④ 必要的口径/局限说明（如数据是否含退款等）。
- 简明专业，不堆砌。
"""

REPORT_USER = """【用户问题】
{question}

【证据（工具返回的真实数据与分析）】
{evidence}

请基于证据撰写最终分析报告。"""


class ReportAgent:
    def __init__(self, client: OpenAI, model: str):
        self.client = client
        self.model = model

    @observe(name="report-agent")
    def write(self, question: str, evidence: str) -> str:
        messages = [
            {"role": "system", "content": REPORT_SYSTEM},
            {
                "role": "user",
                "content": REPORT_USER.format(question=question, evidence=evidence),
            },
        ]
        resp = self.client.chat.completions.create(
            model=self.model, temperature=0, messages=messages
        )
        return resp.choices[0].message.content or ""
