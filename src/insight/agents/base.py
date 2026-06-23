"""通用自我纠错 Agent 基类：生成 → 执行 → 报错喂回改了重试（带预算）。

循环只写在 _run 里，SQL agent 与代码分析 agent 共用；
各子类用一个带 @observe(name=...) 的薄 run 去包 _run，从而在 trace 里有各自的名字。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AgentResult:
    output: str  # 最终（或最后一次）产出的 SQL / 代码
    success: bool
    attempts: int  # 一共试了几次（含首次）
    result: object = None  # 成功时的执行结果（如 (列名, 行) 或 stdout）
    error: str = ""  # 失败时的报错信息


class SelfCorrectingAgent(ABC):
    def __init__(self, max_attempts: int = 3):
        self.max_attempts = max_attempts

    @abstractmethod
    def initial_messages(self, task: str) -> list[dict]:
        """建初始对话（system + 把 task 包成 user）。"""

    @abstractmethod
    def generate(self, messages: list[dict]) -> str:
        """调 LLM，按消息历史产出 SQL / 代码。"""

    @abstractmethod
    def execute(self, output: str) -> tuple[bool, object, str]:
        """执行产出。返回 (是否成功, 结果, 错误信息)。"""

    def feedback(self, error: str) -> str:
        """报错后追加给模型的纠错提示；子类可覆盖。"""
        return f"上面的输出执行报错：\n{error}\n请修正后重新输出。"

    def _run(self, task: str) -> AgentResult:
        """生成→执行→报错喂回重试（带预算）。循环只写这一遍；子类用带 @observe 的 run 包它。"""
        messages = self.initial_messages(task)
        output = ""
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            output = self.generate(messages)
            ok, result, error = self.execute(output)
            if ok:
                return AgentResult(output, True, attempt, result=result)
            last_error = error
            messages.append({"role": "assistant", "content": output})
            messages.append({"role": "user", "content": self.feedback(error)})
        return AgentResult(output, False, self.max_attempts, error=last_error)
