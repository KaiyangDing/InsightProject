"""Critic：忠实性审查员——判断"待审回答"是否忠实于"证据"且真正回答了问题。

在 supervisor 里用作"终答闸门"：编排器给最终回答前先过 Critic，
不通过就把意见喂回去让它修正（系统级自我纠错）。
"""

import json
from dataclasses import dataclass

from langfuse import observe
from openai import OpenAI


@dataclass
class Critique:
    approved: bool
    feedback: str  # 不通过时指出问题+修正方向；通过时简述理由


CRITIC_SYSTEM = """你是一名严格的数据分析审查员（critic）。会给你：用户问题、一份"证据"（系统通过工具取到的真实数据）、一份"待审回答"。
判断这份回答是否【忠实于证据】且【真正回答了问题】。

重点检查：
- 回答里每个数字/结论，是否都能在证据中找到支撑？有没有臆造、夸大、张冠李戴？
- 有没有"偷换口径"：证据里没有的字段/口径被换成别的还不声明（如问"邮箱"却用"姓名"答）？
- 是否真正回答了用户问题（范围、口径对得上）？
- 业务口径是否该提示（如"销售额"是否应排除退款订单，而证据未区分）？

审查完成后，调用工具 submit_critique 提交你的裁决（approved 与 feedback）。
"""

CRITIC_USER = """【用户问题】
{question}

【证据（工具返回的真实数据）】
{evidence}

【待审回答】
{answer}

请审查并调用 submit_critique 提交你的裁决。"""

CRITIQUE_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_critique",
        "description": "提交对回答的审查裁决。",
        "parameters": {
            "type": "object",
            "properties": {
                "approved": {
                    "type": "boolean",
                    "description": "回答是否忠实于证据且真正回答了问题。",
                },
                "feedback": {
                    "type": "string",
                    "description": "approved=false 时指出具体问题与修正方向；approved=true 时一句话说明通过理由。",
                },
            },
            "required": ["approved", "feedback"],
        },
    },
}


class CriticAgent:
    def __init__(self, client: OpenAI, model: str):
        self.client = client
        self.model = model

    @observe(name="critic-agent")
    def review(self, question: str, answer: str, evidence: str) -> Critique:
        messages = [
            {"role": "system", "content": CRITIC_SYSTEM},
            {
                "role": "user",
                "content": CRITIC_USER.format(
                    question=question, evidence=evidence, answer=answer
                ),
            },
        ]
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=messages,
            tools=[CRITIQUE_TOOL],
            tool_choice={
                "type": "function",
                "function": {"name": "submit_critique"},
            },
            extra_body={
                "enable_thinking": False
            },  # ← qwen3 思考模式不支持强制 tool_choice，关掉
        )
        return self._parse(resp.choices[0].message)

    @staticmethod
    def _parse(message) -> Critique:
        tool_calls = message.tool_calls or []
        if not tool_calls:  # 兜底：模型没按要求调工具
            return Critique(True, "(critic 未返回裁决，默认放行)")
        try:
            data = json.loads(tool_calls[0].function.arguments or "{}")
            return Critique(bool(data["approved"]), str(data.get("feedback", "")))
        except (json.JSONDecodeError, KeyError, TypeError):
            return Critique(True, "(critic 裁决无法解析，默认放行)")
