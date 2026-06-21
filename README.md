# Insight · 自主数据分析 Agent

> 把自然语言问题转成 SQL、在数据库上**自主执行**、在 **Docker 沙箱**里跑 pandas 做进阶分析与画图，并具备**自我纠错**、**全链路可观测**与**可复现评测**的数据分析 Agent。
>
> 🚧 进行中的个人项目 · **Week 1–2 已完成** · 目标是演进为多智能体的自主数据分析系统。

---

## ✨ 项目亮点

- 🧠 **自我纠错 Agent** —— `plan → act → observe → 修正重试` 的循环，带步数预算"刹车"；SQL 与代码分析两个 agent **共用一个 `SelfCorrectingAgent` 基类**（循环只写一遍）。
- 🔒 **只读 SQL 执行** —— SQLite 以 URI `mode=ro` 打开，从根上杜绝写操作；附 `SELECT` 护栏与行数上限。
- 🐳 **安全的代码执行与画图** —— LLM 生成的 pandas/matplotlib 代码跑在 **Docker 沙箱**里：断网、限内存/CPU/进程、只读文件系统、非 root、容器即弃。**有安全测试背书**（容器内联网被挡的测试通过）。图表（中文 + seaborn 风格）经 base64 穿过隔离回传主机。
- 📈 **全链路可观测** —— 自托管 **Langfuse**：每次 LLM 调用的 prompt / token / 延迟、agent 重试的层级 trace 全部可视化。
- 📊 **可复现的评测** —— 生成与打分**分离**（冻结预测 → 确定性打分），消除重生成噪声。
- 📐 **贴近官方的 EX 度量** —— 列顺序无关的结果集比对（排列匹配），并对简化做**诚实标注**。
- 🧩 **清晰的异常分层** —— 致命错 vs Agent 可恢复错，由异常类型决定处理策略。
- 🔬 **假设驱动的实验** —— 先分析错因、预测干预效果，再隔离变量做对照实验验证。
- ✅ **核心逻辑全测试** —— pytest（22 个），用"假 LLM"做确定性测试；Docker 相关测试无环境时自动跳过。

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

## 🏗️ 架构

```
自然语言问题
     │
     ▼   ← Langfuse 全程 trace（每步 LLM 调用 / token / 延迟）
┌──────────────────────────────────────────────┐
│  Text2SQLAgent（自我纠错循环）                  │
│    生成 SQL → 只读执行 → 报错喂回重试（带预算）  │
└───────────────┬──────────────────────────────┘
                │ SQL 结果（列名 + 行）
                ▼
┌──────────────────────────────────────────────┐
│  CodeAnalysisAgent（自我纠错循环，共用基类）    │
│    LLM 写 pandas/matplotlib 代码 →【Docker 沙箱】│
│    数据 JSON 注入容器、图表 base64 回传          │
└──────────────────────────────────────────────┘

评测流水线（生成 / 打分分离，确定性可复现）：
  download_spider → predict_spider(冻结预测) → score_spider(EX 打分)
```

> 两个 agent 都继承 `SelfCorrectingAgent`（生成→执行→报错重试循环只写一遍）。
> 交互 demo：`ask.py`（text2SQL）、`analyze.py`（沙箱 pandas 分析）、`chart.py`（沙箱画图）。
> 规划中的演进见 [docs/PROJECT-SPEC.md](docs/PROJECT-SPEC.md)：多智能体编排（Orchestrator / Analyst / Critic / Report）、模型路由降本。

---

## 🛠️ 技术栈

| 类别 | 选型 |
|---|---|
| 语言 / 工具链 | Python 3.13、[uv](https://github.com/astral-sh/uv)、ruff、pytest |
| 模型 | 阿里云百炼 / DashScope（`qwen-plus`，OpenAI 兼容端点，可插拔） |
| 配置 | pydantic-settings（`SecretStr` 保护 key、`lru_cache` 懒加载单例） |
| 数据 / 分析 / 画图 | SQLite（只读访问层）、pandas、matplotlib（含中文字体） |
| 代码沙箱 | Docker（断网 / 限资源 / 只读 fs / 非 root / 即弃） |
| 可观测 | Langfuse（自托管） |
| 评测 | Spider dev 子集 + 自建 EX 度量 |

---

## 📁 项目结构

```
InsightProject/
├── src/insight/
│   ├── config.py          # 配置中心 get_settings()
│   ├── paths.py           # 路径中心（锚定项目根，CWD 无关）
│   ├── llm.py             # LLM 客户端工厂（含 Langfuse 自动 trace）
│   ├── agent_base.py      # SelfCorrectingAgent 基类（生成→执行→纠错循环，只写一遍）
│   ├── text2sql.py        # 问题 → SQL 生成（few-shot, temperature=0）
│   ├── text2sql_agent.py  # Text2SQLAgent（SQL 自我纠错，薄子类）
│   ├── analysis.py        # pandas 代码生成 + 数据注入 + 图表回传
│   ├── analysis_agent.py  # CodeAnalysisAgent（沙箱 pandas 分析/画图，薄子类）
│   ├── db.py              # 只读 SQLite 访问层
│   ├── code_exec.py       # 代码执行器：子进程 / Docker 沙箱 两后端
│   ├── errors.py          # 异常分层
│   └── evaluation.py      # EX 结果集比对（列序无关）
├── scripts/
│   ├── ask.py             # demo（自然语言 → SQL → 结果）
│   ├── analyze.py         # demo（SQL → 沙箱 pandas 进阶分析）
│   ├── chart.py           # demo（SQL → 沙箱 matplotlib 画图 → chart.png）
│   ├── init_db.py         # 生成示例电商库
│   └── download/predict/score_spider.py   # Spider 评测流水线
├── tests/                 # pytest（纠错 / 护栏 / EX / 代码执行 / 分析）
├── sandbox/Dockerfile     # 沙箱镜像（python + pandas + matplotlib + 中文字体，非 root）
├── docs/                  # PROJECT-SPEC、面试速通清单
└── pyproject.toml
```
> 随着 Week 3 多智能体落地，`src/insight/` 会重构为 `tools/` `agents/` `eval/` 子包。

---

## 🚀 快速开始

```bash
# 1. 依赖
uv sync

# 2. 配置百炼 API Key（环境变量；也可写进 .env）
#    Windows : setx DASHSCOPE_API_KEY "sk-xxxx"
#    macOS/Linux : export DASHSCOPE_API_KEY=sk-xxxx

# 3. 生成示例库 + text2SQL demo
uv run scripts/init_db.py
uv run scripts/ask.py "各品类的总销售额是多少？按从高到低排序。"

# 4. 代码执行 / 画图 demo（需先构建沙箱镜像）
docker build -t insight-sandbox sandbox/      # 一次（含 pandas/matplotlib/中文字体）
uv run scripts/analyze.py                     # SQL → 沙箱 pandas 算占比
uv run scripts/chart.py                       # SQL → 沙箱 matplotlib 画图（生成 chart.png）
```

> **可观测（可选）**：自托管 Langfuse（官方仓库 `docker compose up`），设好 `LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST` 后，所有 LLM 调用会自动上报到 `http://localhost:3000`。

## 📊 复现 Spider 评测

```bash
uv run scripts/download_spider.py   # 下载偏难子集（99 题 / 20 库）
uv run scripts/predict_spider.py    # 生成并冻结预测（调一次模型）
uv run scripts/score_spider.py      # 计算 EX（不调模型，确定性）
```

## ✅ 测试

```bash
uv run pytest -q     # 22 passed（Docker 相关测试无环境时自动 skip）
```

---

## 🗺️ Roadmap

- [x] **Week 1** —— 单 Agent text2SQL + 只读执行 + 自我纠错 + 单元测试
- [x] Spider 基线 EX（生成/打分分离、确定性、诚实标注）
- [x] **Week 2** —— Langfuse 可观测 + Docker 沙箱 code execution（pandas + 画图）
- [ ] **Week 3** —— 多智能体（Orchestrator / Analyst / Critic / Report）+ 长链路归因
- [ ] **Week 4** —— 完整 eval harness + 模型路由降本 + Streamlit demo
- [ ] 长期 —— MCP 多数据源、跨会话记忆、更多行业数据集

---

## 🔧 工程笔记（一些刻意的设计）

- **代码沙箱即安全边界**：LLM 生成的代码只在 Docker 容器里跑——`--network none` 断网、`--memory/--cpus/--pids-limit` 限资源、`--read-only` 不可写盘、非 root、`--rm` 即弃；**不向容器传任何 secret**。有"联网被挡"的测试背书。
- **数据怎么进沙箱、图怎么出沙箱**：容器读不到主机数据 → 把 SQL 结果序列化成 JSON 随代码注入、容器内还原成 `df`；图表则在沙箱里存成 PNG → base64 打印 → 主机解码——隔离与取数/取图两全。
- **一个自我纠错基类，两处复用**：SQL 与代码分析的纠错循环结构相同，抽出 `SelfCorrectingAgent` 基类，两个 agent 只填"建消息 / 怎么生成 / 怎么执行"三个钩子，循环只写一遍。
- **可观测零侵入**：`llm.py` 一行换成 `langfuse.openai` 包装即自动 trace；agent `run()` 加 `@observe` 把一次调用归为一条层级 trace；测试侧关掉 tracing 保持与外部解耦。
- **异常分层即策略**：`SQLExecutionError`（可恢复）被 Agent 喂回重试；`DatabaseNotReadyError`（致命）抛到顶层——**用类型而非 if/else 决定处理**。
- **可复现评测**：模型只跑一次、预测落盘；改度量只需重新打分，不被重生成噪声污染。
- **踩过的真实坑**：matplotlib 画中文要设 `font.sans-serif`（不是 `font.family`）且必须在画图前；seaborn `set_theme` 会重置字体（故改用 matplotlib 内置 `seaborn-v0_8` 风格）；Docker 镜像改了依赖/字体**必须 rebuild**。
- **CWD 无关路径**：所有路径锚定项目根（`Path(__file__).parents[...]`），从任意目录 / IDE 运行都不会找不到文件。

---

📄 完整设计文档：[docs/PROJECT-SPEC.md](docs/PROJECT-SPEC.md) · 仓库：<https://github.com/KaiyangDing/InsightProject>
