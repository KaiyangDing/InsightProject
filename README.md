# Insight · 自主数据分析 Agent

一个多智能体、可自主执行长链路分析、结论可溯源的 AI 数据分析师。

详见 [项目说明文档](docs/PROJECT-SPEC.md)。

## 快速开始

```bash
# 安装依赖（uv 按 pyproject.toml 同步出 .venv）
uv sync

# 运行 Hello 百炼（需已在系统环境变量设好 DASHSCOPE_API_KEY）
uv run scripts/hello_bailian.py
```