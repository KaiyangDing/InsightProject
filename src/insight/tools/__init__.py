"""能力层（tools）：agent 与外部世界打交道的工具。

- llm        ：构造指向百炼的 LLM 客户端（带 Langfuse 自动 trace）。
- db         ：只读 SQLite 数据访问层。
- code_exec  ：代码执行器（子进程 / Docker 沙箱两后端）。

这些工具不含编排逻辑，构造时被注入到 agent 里（依赖注入，便于替换/测试）。
"""

from insight.tools.code_exec import CodeExecutor, DockerCodeExecutor, ExecutionResult
from insight.tools.db import Database
from insight.tools.llm import get_chat_client

__all__ = [
    "get_chat_client",
    "Database",
    "CodeExecutor",
    "DockerCodeExecutor",
    "ExecutionResult",
]
