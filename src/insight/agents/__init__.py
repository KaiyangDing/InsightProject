"""Agent 层：自我纠错的编排逻辑。

- base           ：SelfCorrectingAgent 基类（生成→执行→报错重试循环，只写一遍）+ AgentResult。
- text2sql       ：问题→SQL 的纯生成（prompt + few-shot）。
- text2sql_agent ：Text2SQLAgent —— 在 db 上执行 SQL 并自我纠错。
- analysis       ：问题→pandas 代码的纯生成 + 数据注入 / 图表回传。
- analysis_agent ：CodeAnalysisAgent —— 在沙箱执行代码并自我纠错。

每个 agent = 一个"生成"模块（prompt）+ 一个"agent"模块（填基类的三个钩子）。
"""

from insight.agents.analysis_agent import CodeAnalysisAgent
from insight.agents.base import AgentResult, SelfCorrectingAgent
from insight.agents.text2sql_agent import Text2SQLAgent

__all__ = [
    "SelfCorrectingAgent",
    "AgentResult",
    "Text2SQLAgent",
    "CodeAnalysisAgent",
]
