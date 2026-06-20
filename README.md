# Insight · 自主数据分析 Agent

> 把自然语言问题转成 SQL、在数据库上**自主执行**、并具备**自我纠错**与**可复现评测**的 text-to-SQL Agent。
>
> 🚧 进行中的个人项目 · **Week 1 已完成** · 目标是逐步演进为多智能体的自主数据分析系统。

---

## ✨ 项目亮点

- 🧠 **自我纠错 Agent** —— `plan → act → observe → 修正重试` 的循环，带步数预算"刹车"防死循环。
- 🔒 **只读沙箱执行** —— SQLite 以 URI `mode=ro` 打开，从根上杜绝写操作；附 `SELECT` 护栏与行数上限。
- 📊 **可复现的评测** —— 生成与打分**分离**（冻结预测 → 确定性打分），消除 `temperature=0` 下仍存在的重生成噪声。
- 📐 **贴近官方的 EX 度量** —— 列顺序无关的结果集比对（排列匹配），并对度量的简化做**诚实标注**。
- 🧩 **清晰的异常分层** —— 区分"致命错（开发者修）"与"Agent 可恢复错（喂回模型重试）"，由异常类型决定处理策略。
- ✅ **核心逻辑全测试** —— pytest 用“假 LLM”对纠错循环、只读护栏、EX 比对做**确定性**测试。
- 🔬 **假设驱动的实验** —— 先分析错因、预测干预效果，再隔离变量做对照实验验证（few-shot、自我纠错增益）。

---

## 📈 评测结果（Spider dev）

在 **Spider dev 的一个偏难子集**（按 gold SQL 复杂度启发式抽样，**99 题、跨 20 个数据库**）上：

| 指标 | 结果 |
|---|---|
| 单次生成 EX（原始） | **≈ 73%** |
| 剔除 gold 标注错 + 重复行/并列度量伪差后（真实水平估计） | **≈ 85%** |
| 模型 | 阿里云百炼 `qwen-plus`（OpenAI 兼容端点） |

> **诚实标注**：这是**列顺序无关的简化版 EX**，不等于官方 test-suite EX；数据取自 HF 镜像 `prem-research/spider`，已核验内容 = 官方 dev（1034 题 / 20 库）。
> 对错例的逐条分析发现：约 1/4 的"错"其实是 **gold 标注瑕疵**（错误大小写字面值、`SELECT *`、重复行 / 并列第一），并非模型错误——故同时给出剔除后的估计区间。
> （在一个偏易的 50 题子集上，单次 EX ≈ 94%。）

### 几个有价值的发现（“生成 / 打分分离”让它们得以干净测量）

**① few-shot：“生效 ≠ 涨分”** —— 给模型加 few-shot（教 `INTERSECT/EXCEPT/UNION`）后，模型 SQL 的写法**确实改对了**，但聚合 EX 几乎没动：该子集的剩余误差被 **gold 噪声 + 度量边界**主导。教训——**必须看 SQL，而非只看分数。**

**② 单次 vs 自我纠错 Agent：一次干净的对照实验**

| 方案 | EX |
|---|---|
| 单次生成（few-shot） | 73.7% |
| + 自我纠错 Agent | 74.7%（+1，噪声范围内） |

流程：**分析错因**（错误几乎都是“能执行、但结果错”的语义错，而非语法错）→ **预测**自我纠错（execution-retry）无效 → **隔离变量**做对照 → +1%（噪声内）**证实预测**。
结论：在 Spider 这类“题目对应干净 schema”的基准上，自我纠错对准确率**无可测量贡献**；它的价值在**产品鲁棒性**（交互场景下用户随口提问易产生非法 SQL），而非刷基准分。

---

## 🏗️ 架构（当前）

```
自然语言问题
     │
     ▼
┌──────────────────────────────────────────────┐
│  Text2SQLAgent  (自我纠错循环)                  │
│    build_messages(few-shot) → request_sql      │
│         │  生成 SQL                             │
│         ▼                                       │
│    Database.run_query  (只读执行)               │
│         ├─ 成功 → 返回结果(列名 + 行)            │
│         └─ SQLExecutionError → 错误喂回 → 重试   │
│            （预算 max_attempts 次）             │
└──────────────────────────────────────────────┘

评测流水线（生成 / 打分分离，确定性可复现）：
  download_spider → predict_spider(冻结预测) → score_spider(EX 打分)
```

> 交互 demo（`ask.py`）走完整的自我纠错 Agent；Spider 基线则用**单次生成**测量（更干净的能力基准）。
> 规划中的演进方向见 [docs/PROJECT-SPEC.md](docs/PROJECT-SPEC.md)：多智能体编排（Orchestrator / SQL / Analyst / Critic / Report）、code execution（pandas）、Langfuse 可观测、模型路由降本。

---

## 🛠️ 技术栈

| 类别 | 选型 |
|---|---|
| 语言 / 工具链 | Python 3.13、[uv](https://github.com/astral-sh/uv)、ruff、pytest |
| 模型 | 阿里云百炼 / DashScope（`qwen-plus`，OpenAI 兼容端点，可插拔） |
| 配置 | pydantic-settings（`SecretStr` 保护 key、`lru_cache` 懒加载单例） |
| 数据 | SQLite（只读访问层） |
| 评测 | Spider dev 子集 + 自建 EX 度量 |

---

## 📁 项目结构

```
InsightProject/
├── src/insight/
│   ├── config.py          # 配置中心 get_settings()
│   ├── paths.py           # 路径中心（锚定项目根，CWD 无关）
│   ├── llm.py             # LLM 客户端工厂（统一适配层）
│   ├── text2sql.py        # 问题 → SQL（few-shot, temperature=0）
│   ├── db.py              # 只读 SQLite 访问层
│   ├── agent.py           # 自我纠错 Agent
│   ├── errors.py          # 异常分层
│   └── evaluation.py      # EX 结果集比对（列序无关）
├── scripts/
│   ├── ask.py             # 交互 demo（自然语言 → SQL → 结果）
│   ├── init_db.py         # 生成示例电商库
│   ├── download_spider.py # 下载 Spider 偏难子集（难度启发式）
│   ├── predict_spider.py  # 生成并冻结预测
│   └── score_spider.py    # 确定性 EX 打分
├── tests/                 # pytest（纠错循环 / 只读护栏 / EX 比对）
├── docs/                  # PROJECT-SPEC、面试速通清单
└── pyproject.toml
```

---

## 🚀 快速开始

```bash
# 1. 安装依赖（uv 按 pyproject.toml 同步出 .venv）
uv sync

# 2. 配置百炼 API Key（环境变量；也可写进 .env）
#    Windows : setx DASHSCOPE_API_KEY "sk-xxxx"
#    macOS/Linux : export DASHSCOPE_API_KEY=sk-xxxx

# 3. 生成示例库并跑一个交互 demo
uv run scripts/init_db.py
uv run scripts/ask.py "各品类的总销售额是多少？按从高到低排序。"
```

## 📊 复现 Spider 评测

```bash
uv run scripts/download_spider.py   # 下载偏难子集（99 题 / 20 库）
uv run scripts/predict_spider.py    # 生成并冻结预测（调一次模型）
uv run scripts/score_spider.py      # 计算 EX（不调模型，确定性）
```

## ✅ 测试

```bash
uv run pytest -v
```

---

## 🗺️ Roadmap

- [x] **Week 1** —— 单 Agent text2SQL + 只读执行 + 自我纠错 + 单元测试
- [x] Spider 基线 EX（生成/打分分离、确定性、诚实标注）
- [ ] **Week 2** —— Langfuse 可观测 + code execution（pandas / 画图）
- [ ] **Week 3** —— 多智能体（Orchestrator / Analyst / Critic / Report）+ 长链路归因
- [ ] **Week 4** —— 完整 eval harness + 模型路由降本 + Streamlit demo
- [ ] 长期 —— MCP 多数据源、跨会话记忆、更多行业数据集

---

## 🔧 工程笔记（一些刻意的设计）

- **只读沙箱**：Agent 运行时永远只读，写库只发生在开发期的 `init_db`；`run_query` 把底层 sqlite 错误包装成带上下文的 `SQLExecutionError`。
- **异常分层即策略**：`SQLExecutionError`（可恢复）会被 Agent 捕获并喂回模型重试；`DatabaseNotReadyError`（致命）则一路抛到顶层——**用类型而非 if/else 决定处理策略**。
- **可复现评测**：模型只跑一次、预测落盘；改度量只需重新打分，不被重生成噪声污染。
- **诚实的度量**：EX 列序无关（贴近官方语义），并明确标注其简化点与 gold 数据的已知瑕疵——基准分数要带着批判看。
- **CWD 无关路径**：所有路径锚定到项目根（`Path(__file__).parents[...]`），从任意目录 / IDE 运行都不会找不到文件。

---

📄 完整设计文档：[docs/PROJECT-SPEC.md](docs/PROJECT-SPEC.md) · 仓库：<https://github.com/KaiyangDing/InsightProject>
