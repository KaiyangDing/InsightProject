"""代码分析 agent：自我纠错循环的 pandas 实现（继承 SelfCorrectingAgent）。

循环在 base._run，这里填三个钩子 + 一个带名字的 run（用于 trace 区分）。
"""

from langfuse import observe
from openai import OpenAI

from insight.agents.base import AgentResult, SelfCorrectingAgent
from insight.agents.analysis import (
    build_analysis_code,
    build_pandas_messages,
    request_pandas_code,
)


class CodeAnalysisAgent(SelfCorrectingAgent):
    def __init__(
        self,
        client: OpenAI,
        model: str,
        executor,
        columns: list[str],
        rows: list[tuple],
        max_attempts: int = 3,
    ):
        super().__init__(max_attempts)
        self.client = client
        self.model = model
        self.executor = executor
        self.columns = columns
        self.rows = rows

    @observe(name="code-analysis-agent")
    def run(self, question: str) -> AgentResult:
        return self._run(question)

    def initial_messages(self, question: str) -> list[dict]:
        return build_pandas_messages(question, self.columns, self.rows)

    def generate(self, messages: list[dict]) -> str:
        return request_pandas_code(self.client, self.model, messages)

    def execute(self, code: str) -> tuple[bool, object, str]:
        r = self.executor.run(build_analysis_code(self.columns, self.rows, code))
        return r.success, r.stdout, r.error

    def feedback(self, error: str) -> str:
        return f"上面的代码执行报错：\n{error}\n请修正后重新输出 pandas 代码（只输出代码）。"
