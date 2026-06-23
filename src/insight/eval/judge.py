"""LLM-as-judge：用一个"裁判"模型给报告按 rubric 打分（忠实性 / 相关性）。

为什么用 judge：报告/分析质量没法用规则自动评，让模型按 rubric 评分是 LLM 应用的标准做法。
注意 judge 也会犯错，故 ①用强模型 ②给明确 rubric ③主要看相对比较/趋势，不当绝对真值。
"""

import json
from dataclasses import dataclass

from langfuse import observe
from openai import OpenAI


@dataclass
class Judgment:
    faithfulness: int  # 1-5：报告内容是否忠实于证据（不臆造）
    relevance: int  # 1-5：是否真正、完整地回答了用户问题
    rationale: str  # 简短打分理由


JUDGE_SYSTEM = """你是一名严格的评测裁判。会给你：用户问题、证据（系统取到的真实数据）、以及一份待评的分析报告。
按 rubric 给报告打分（1-5，5 最好）：
- faithfulness（忠实性）：报告里的数字/结论是否都由证据支撑，有没有臆造/夸大/偷换口径。
- relevance（相关性）：报告是否真正、完整地回答了用户问题。
评分要克制：有明显臆造给 1-2；完全忠实且切题给 5。评完调用 submit_judgment 提交。"""

JUDGE_USER = """【用户问题】
{question}

【证据】
{evidence}

【待评报告】
{report}

请评分并调用 submit_judgment。"""

JUDGMENT_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_judgment",
        "description": "提交对报告的评分。",
        "parameters": {
            "type": "object",
            "properties": {
                "faithfulness": {"type": "integer", "description": "忠实性 1-5"},
                "relevance": {"type": "integer", "description": "相关性 1-5"},
                "rationale": {"type": "string", "description": "简短打分理由"},
            },
            "required": ["faithfulness", "relevance", "rationale"],
        },
    },
}


class Judge:
    def __init__(self, client: OpenAI, model: str):
        self.client = client
        self.model = model

    @observe(name="judge")
    def judge(self, question: str, evidence: str, report: str) -> Judgment:
        messages = [
            {"role": "system", "content": JUDGE_SYSTEM},
            {
                "role": "user",
                "content": JUDGE_USER.format(
                    question=question, evidence=evidence, report=report
                ),
            },
        ]
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=messages,
            tools=[JUDGMENT_TOOL],
            tool_choice={"type": "function", "function": {"name": "submit_judgment"}},
        )
        return self._parse(resp.choices[0].message)

    @staticmethod
    def _parse(message) -> Judgment:
        tool_calls = message.tool_calls or []
        if not tool_calls:  # 裁判没按要求调工具
            return Judgment(0, 0, "(judge 未返回评分)")
        try:
            data = json.loads(tool_calls[0].function.arguments or "{}")
            return Judgment(
                int(data["faithfulness"]),
                int(data["relevance"]),
                str(data.get("rationale", "")),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return Judgment(0, 0, "(judge 评分无法解析)")
