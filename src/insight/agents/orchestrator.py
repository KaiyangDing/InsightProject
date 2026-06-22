"""LLM 驱动的编排器：把子 agent 当"工具"，由 LLM 自主决定调用顺序/次数/何时停。

基于 OpenAI 兼容的原生 function calling：
  循环 = 带 tools 调 LLM → 拿到 tool_calls → 执行 → 结果喂回 → 再调 …… → 无 tool_calls 即终答。
带 max_steps 预算，防止无限自主执行（呼应 SelfCorrectingAgent 的 max_attempts）。
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


ORCHESTRATOR_SYSTEM = """你是一个数据分析任务的编排器（orchestrator）。
你不直接查数据库或写代码，而是调用下列工具来完成用户的问题，信息足够后给出最终的自然语言结论。

原则：
- 先想清楚要哪些数据，再调用工具；不要臆造工具没返回的数据。
- 一个工具结果不够就继续调别的工具；信息足够了就直接输出给用户的最终回答（此时不要再调工具）。
- 最终回答必须忠实于工具返回的真实结果。
"""


class Orchestrator:
    def __init__(
        self, client: OpenAI, model: str, tools: list[Tool], max_steps: int = 6
    ):
        self.client = client
        self.model = model
        self.tools = {t.name: t for t in tools}  # 名字 → Tool，便于分发
        self.max_steps = max_steps
        self.workspace = Workspace()

    @observe(name="orchestrator")
    def run(self, question: str) -> OrchestratorResult:
        messages = [
            {"role": "system", "content": ORCHESTRATOR_SYSTEM},
            {"role": "user", "content": question},
        ]
        tool_schemas = [t.schema() for t in self.tools.values()]
        called = []

        for step in range(1, self.max_steps + 1):
            resp = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=messages,
                tools=tool_schemas,  # ← 把工具清单交给模型
            )
            msg = resp.choices[0].message

            # 模型不再要工具 → 这就是最终回答，结束
            if not msg.tool_calls:
                return OrchestratorResult(msg.content or "", step, called)

            # 把助手这条（含 tool_calls）加回历史——tool 结果必须紧跟在它后面
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

            # 逐个执行工具，结果作为 role:"tool" 消息喂回（靠 tool_call_id 对应）
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

        # 预算耗尽仍没给终答
        return OrchestratorResult(
            "（达到步数上限仍未得出结论）", self.max_steps, called
        )
