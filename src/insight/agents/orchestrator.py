"""LLM 驱动的编排器：把子 agent 当"工具"，由 LLM 自主决定调用顺序/次数/何时停。

基于 OpenAI 兼容的原生 function calling：
  循环 = 带 tools 调 LLM → 拿到 tool_calls → 执行 → 结果喂回 → 再调 …… → 无 tool_calls 即终答。
带 max_steps 预算；预算耗尽时返回"最近一次产出的报告"（优雅降级，不丢弃工作）。
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field

from langfuse import observe
from openai import OpenAI


@dataclass
class Workspace:
    """子 agent 之间共享的"黑板"：大数据（表、图）放这里，LLM 上下文只传摘要/引用。"""

    artifacts: dict = field(default_factory=dict)

    def put(self, key: str, value) -> None:
        self.artifacts[key] = value

    def get(self, key: str):
        return self.artifacts.get(key)


@dataclass
class Tool:
    """一个可被编排器调用的工具（通常包了一个子 agent）。"""

    name: str
    description: str
    parameters: dict  # JSON Schema，描述入参（告诉模型怎么调）
    handler: Callable  # (workspace, **kwargs) -> str（回给 LLM 看的文本结果）

    def schema(self) -> dict:
        """转成 OpenAI tools 数组要的格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


@dataclass
class OrchestratorResult:
    answer: str
    steps: int  # 一共转了几步
    tool_calls: list  # 调了哪些工具（名字+入参），用于复盘/归因
    reviews: int = 0  # 经过几轮 Critic 审查（默认 0，向后兼容）
    evidence: str = ""  # 报告所依据的证据（工具返回的真实数据），供评测/调试


ORCHESTRATOR_SYSTEM = """你是一个数据分析任务的编排器（orchestrator）。
你不直接查数据库或写代码，而是调用下列工具来完成用户的问题，信息足够后给出最终的自然语言结论。

原则：
- 若问题依赖一个数据里没有定义的业务概念，不要把某个假定口径当事实，最终回答要如实声明该假设。
- 先想清楚要哪些数据，再调用工具；不要臆造工具没返回的数据。
- 一个工具结果不够就继续调别的工具；信息足够了就直接输出给用户的最终回答（此时不要再调工具）。
- 最终回答必须忠实于工具返回的真实结果。
- 不要用近似问题反复取数。若一两次调用后仍拿不到能回答问题的数据（结果为空、所需字段不存在等），就【停止调用工具】，直接基于已有结果如实作答（说明无法回答及原因）。
"""

REVISE_TEMPLATE = (
    "审查未通过：{feedback}\n请据此修正你的最终回答；如需核实数据可再调用工具。"
)


class Orchestrator:
    def __init__(
        self,
        client: OpenAI,
        model: str,
        tools: list[Tool],
        max_steps: int = 6,
        critic=None,
        max_reviews: int = 2,
        report=None,  # 鸭子类型：任何带 .write(question, evidence) 的对象
    ):
        self.client = client
        self.model = model
        self.tools = {t.name: t for t in tools}
        self.max_steps = max_steps
        self.critic = critic
        self.max_reviews = max_reviews
        self.report = report
        self.workspace = Workspace()

    @observe(name="orchestrator")
    def run(self, question: str) -> OrchestratorResult:
        messages = [
            {"role": "system", "content": ORCHESTRATOR_SYSTEM},
            {"role": "user", "content": question},
        ]
        tool_schemas = [t.schema() for t in self.tools.values()]
        called = []
        reviews_done = 0
        last_candidate = ""
        last_evidence = ""

        for step in range(1, self.max_steps + 1):
            resp = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=messages,
                tools=tool_schemas,
            )
            msg = resp.choices[0].message

            # 模型不再要工具 → 该收尾了
            if not msg.tool_calls:
                # 证据 = 工具返回的真实数据（给 Report 写 / 给 Critic 审）
                evidence = "\n\n".join(
                    m["content"] for m in messages if m.get("role") == "tool"
                )
                # 有 Report agent → 用它从证据合成报告；否则用编排器自己的话
                candidate = (
                    self.report.write(question, evidence)
                    if self.report is not None
                    else (msg.content or "")
                )
                last_candidate, last_evidence = candidate, evidence

                # 没挂 Critic，或评审预算用尽 → 直接采纳
                if self.critic is None or reviews_done >= self.max_reviews:
                    return OrchestratorResult(
                        candidate, step, called, reviews_done, evidence
                    )

                # 过 Critic 闸门（审的是 candidate，即报告）
                critique = self.critic.review(question, candidate, evidence)
                reviews_done += 1
                if critique.approved:
                    return OrchestratorResult(
                        candidate, step, called, reviews_done, evidence
                    )

                # 不通过 → 候选 + 审查意见一起喂回，继续修
                messages.append({"role": "assistant", "content": candidate})
                messages.append(
                    {
                        "role": "user",
                        "content": REVISE_TEMPLATE.format(feedback=critique.feedback),
                    }
                )
                continue

            # 有 tool_calls → 执行工具
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments or "{}")
                called.append({"name": name, "args": args})
                tool = self.tools.get(name)
                if tool is None:
                    result = f"错误：未知工具 {name}"
                else:
                    try:
                        result = tool.handler(self.workspace, **args)
                    except Exception as e:  # 工具炸了不让编排崩，把错误喂回让 LLM 调整
                        result = f"工具 {name} 执行出错：{e}"
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )

        # 预算耗尽：尽量从已收集的证据产出报告，别返回废话
        evidence = last_evidence or "\n\n".join(
            m["content"] for m in messages if m.get("role") == "tool"
        )
        if last_candidate:
            answer = last_candidate
        elif self.report is not None and evidence:
            answer = self.report.write(question, evidence)
        else:
            answer = "（达到步数上限，未能在预算内完成）"
        return OrchestratorResult(
            answer, self.max_steps, called, reviews_done, evidence
        )
