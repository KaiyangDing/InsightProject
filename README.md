# Insight · 自主数据分析 Agent

> 把自然语言问题转成 SQL、在数据库上**自主执行**、在 **Docker 沙箱**里跑 pandas 做进阶分析与画图，并由 **LLM 编排器（supervisor）自主调度多个子 agent** 协作，具备**自我纠错**、**忠实性审查**、**全链路可观测**与**可复现评测**的数据分析 Agent。
>
> 🚧 进行中的个人项目 · **Week 1–5(A) 已完成** · LLM 编排器自主协调"取数 → 分析 → 审查 → 报告"，跑在 **真实电商数据（Olist）** 上，配 **LLM-as-judge 评测**、**Streamlit demo** 与 **FastAPI + Docker Compose 部署**。

---

## ✨ 项目亮点

- 🧭 **LLM 自主编排（multi-agent supervisor）** —— 编排器用**原生 function calling** 把 SQL / 分析子 agent 当工具，自主决定调谁、调几次、何时停（带 `max_steps` 预算）；收尾由 **Report** 从证据写结构化报告、**Critic** 把关忠实性——**五角色齐**（Orchestrator/SQL/Analyst/Critic/Report）。子 agent 间大数据走 **Workspace 黑板**，回给 LLM 只是摘要。
- 🕵️ **Critic 忠实性闸门** —— 终答前强制过 Critic 审查（拿真实工具结果当证据），不通过把意见喂回重写（`max_reviews` 封顶）——系统级自我纠错，专治"编数 / 偷换口径"。
- 🌐 **真实数据 + 可部署服务** —— 跑在 **Olist 巴西电商真实数据**（9 表 / ~10 万订单）上，配 **schema 上下文层**（注入业务口径 / 品类翻译，治"瞎编口径"）；打包成 **FastAPI REST 服务 + Docker Compose**（含沙箱 DooD），从 demo 到能用。
- 🧠 **自我纠错 Agent** —— `plan → act → observe → 修正重试` 的循环，带步数预算"刹车"；SQL 与代码分析两个 agent **共用一个 `SelfCorrectingAgent` 基类**（循环只写一遍）。
- 🔒 **只读 SQL 执行** —— SQLite 以 URI `mode=ro` 打开，从根上杜绝写操作；附 `SELECT` 护栏与行数上限。
- 🐳 **安全的代码执行与画图** —— LLM 生成的 pandas/matplotlib 代码跑在 **Docker 沙箱**里：断网、限内存/CPU/进程、只读文件系统、非 root、容器即弃。**有安全测试背书**（容器内联网被挡的测试通过）。图表（中文 + seaborn 风格）经 base64 穿过隔离回传主机。
- 📈 **全链路可观测** —— 自托管 **Langfuse**：每次 LLM 调用的 prompt / token / 延迟、agent 重试的层级 trace 全部可视化。
- 📊 **可复现的评测** —— text2SQL 侧生成与打分**分离**（冻结预测 → 确定性打分）消除噪声；多智能体侧用 **LLM-as-judge** 评报告的忠实性/相关性，并做 Critic 有效性 A/B。
- 📐 **贴近官方的 EX 度量** —— 列顺序无关的结果集比对（排列匹配），并对简化做**诚实标注**。
- 🧩 **清晰的异常分层** —— 致命错 vs Agent 可恢复错，由异常类型决定处理策略。
- 🔬 **假设驱动的实验** —— 先分析错因、预测干预效果，再隔离变量做对照实验验证。
- ✅ **核心逻辑全测试** —— pytest（47 个），用"假 LLM"做确定性测试；Docker 相关测试无环境时自动跳过。

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

## 📈 评测结果（Olist 真实电商数据 · schema 上下文层 A/B）

在 **真实 Olist 巴西电商数据**（9 表 / ~10 万订单）上手写 **20 道 (问题, gold SQL)**（重点覆盖业务口径陷阱），对比 text2SQL **带 / 不带 schema 上下文层**（注入销售额口径、客户去重口径、葡→英品类翻译）：

| 方案 | Execution Accuracy |
|---|---|
| 不带 schema 上下文 | **80%** |
| + schema 上下文（业务口径注入） | **95%** |
| **Δ** | **+15pp** |

> **失败全部是真实口径错误**（非 gold 噪声）：不带口径注入时，模型把 `payment_value` 当销售额、用 `customer_id` 当"客户"去重；schema 上下文精确修正了这些业务陷阱。唯一残留失败诚实暴露"prompt 软约束不保证模型一定 JOIN 取对字段"的极限。
> **评测设计教训**：gold 的列集要和问题对齐（问"哪些 X"就只 `SELECT X`，否则 EX 对列数敏感会误判）；EX 里避免"top-N + 并列"题；temp=0 仍有 run-to-run 抖动；**绝不为通过某道题去改 prompt**（= 过拟合 eval）。复现：`uv run scripts/eval/olist_ex.py`

### LLM-as-judge 报告质量评 + 一个诚实的"盲区"发现

用**跨模型裁判**（`qwen-max` 评系统的报告，减同源偏差）对 7 道**开放分析题**（各州分布、复购率、履约率、品类、满意度、支付、时间趋势）跑完整多智能体编排，judge 给**全部 7 份报告打了 5/5**（忠实性 + 相关性）。

> **但没轻信这个满分**——拿数据库**真值逐份核对**后发现：
> - **6/7 确实优秀**：数字逐个对得上真值，连"准时交付率""复购客户分布"这类自算指标都精确。
> - **1 份（品类分析）judge 给高了**：销售额偏 ~0.5%，因 analyst 在 join 评价表时**丢掉了无评价订单**，把"有评价订单的销售额"当成品类总销售额报出。
>
> **关键结论：`judge 5/5 ≠ 数字对`。** LLM-as-judge 测的是"报告 vs 证据"的**忠实性**——报告忠实复述了 analyst 算出的（子集）数字，裁判没有真值、看不出上游算错。**这恰好证明 judge 测忠实性、测不出正确性**：它和 EX（正确性）互补，高风险场景必须配 ground-truth 核对。复现：`uv run scripts/eval/olist_judge.py`

---

## 🏗️ 架构

```
                       自然语言问题
                            │
                            ▼   ← Langfuse 一条嵌套 trace（长链路归因）
              ┌───────────────────────────────┐
              │   Orchestrator（supervisor）    │  原生 function calling 自主编排，
              │   自主决定调谁 / 几次 / 何时停    │  max_steps 预算兜底
              └──────┬──────────────┬──────────┘
          run_sql ▼            analyze_data ▼          （子 agent 各带自我纠错）
       ┌──────────────┐    ┌──────────────────┐
       │ Text2SQLAgent│    │ CodeAnalysisAgent │
       │ NL→SQL→只读   │    │ 沙箱 pandas/画图   │
       └──────┬───────┘    └─────────┬────────┘
              └───── Workspace 黑板 ───┘   表/图等大数据共享，不进 LLM 上下文
                            │
   收尾（信息够了）▼  ReportAgent 从证据写结构化报告  →  CriticAgent 审忠实性
                            │                            不通过 → 打回重修
                            ▼                            （max_reviews 封顶）
                        最终报告

评测流水线（生成 / 打分分离，确定性可复现）：
  download_spider → predict_spider(冻结预测) → score_spider(EX 打分)
```

> SQL / 分析两个子 agent 都继承 `SelfCorrectingAgent`（纠错循环只写一遍）；编排器靠**鸭子类型**接 Critic 与 Report（只依赖 `.review()` / `.write()`，不 import）。
> 交互 demo：`ask.py`（text2SQL）、`analyze.py`（沙箱分析）、`chart.py`（画图）、`orchestrate.py`（**多智能体自主编排**）。
> 更完整的设计与后续方向（模型路由降本等）见 [docs/PROJECT-SPEC.md](docs/PROJECT-SPEC.md)。

---

## 🛠️ 技术栈

| 类别 | 选型 |
|---|---|
| 语言 / 工具链 | Python 3.13、[uv](https://github.com/astral-sh/uv)、ruff、pytest |
| 模型 | 阿里云百炼 / DashScope（`qwen-plus`，OpenAI 兼容端点，可插拔） |
| 配置 | pydantic-settings（`SecretStr` 保护 key、`lru_cache` 懒加载单例） |
| 数据 / 分析 / 画图 | SQLite（只读访问层）、**Olist 真实电商数据**、pandas、matplotlib（含中文字体） |
| 代码沙箱 | Docker（断网 / 限资源 / 只读 fs / 非 root / 即弃） |
| 多智能体编排 | LLM supervisor（agents-as-tools）+ 原生 function calling + Critic 闸门 |
| 可观测 | Langfuse（自托管，含 token / 成本核算） |
| 评测 | Spider EX（text2SQL）+ LLM-as-judge（多智能体报告质量） |
| Web UI / 服务 | Streamlit demo + **FastAPI REST + Docker Compose**（沙箱 DooD） |
| 语义层 | schema 上下文层（业务口径 / 品类翻译注入，"语义层 lite"） |

---

## 📁 项目结构

```
InsightProject/
├── src/insight/            # 分层即包结构
│   ├── config.py           # 基建：配置中心 get_settings()
│   ├── paths.py            # 基建：路径中心（锚定项目根，CWD 无关）
│   ├── errors.py           # 基建：异常分层（致命 vs 可恢复）
│   ├── tools/              # 能力层：与外部世界打交道的工具
│   │   ├── llm.py          #   LLM 客户端工厂（含 Langfuse 自动 trace）
│   │   ├── db.py           #   只读 SQLite 访问层
│   │   └── code_exec.py    #   代码执行器：子进程 / Docker 沙箱 两后端
│   ├── agents/            # 生成 + 自我纠错 + 多智能体编排
│   │   ├── base.py         #   SelfCorrectingAgent 基类（循环只写一遍）+ AgentResult
│   │   ├── text2sql.py     #   问题 → SQL 生成（few-shot, temperature=0）
│   │   ├── text2sql_agent.py  # Text2SQLAgent（SQL 自我纠错，薄子类）
│   │   ├── analysis.py     #   pandas 代码生成 + 数据注入 + 图表回传
│   │   ├── analysis_agent.py  # CodeAnalysisAgent（沙箱 pandas 分析/画图，薄子类）
│   │   ├── orchestrator.py #   Orchestrator(supervisor) + Tool + Workspace 黑板
│   │   ├── agent_tools.py  #   子 agent → 编排器工具（agents-as-tools）
│   │   ├── critic_agent.py #   CriticAgent 忠实性审查（function calling 裁决）
│   │   ├── report_agent.py #   ReportAgent 从证据写结构化报告
│   │   └── schema_context.py  # schema 上下文层（注入业务口径/品类翻译，"语义层 lite"）
│   └── eval/              # 评测层
│       ├── evaluation.py   #   Spider EX 结果集比对（列序无关）
│       ├── judge.py        #   LLM-as-judge（function calling 给报告打分）
│       └── agent_eval.py   #   多智能体端到端评测 + Critic A/B
├── scripts/
│   ├── init_db.py         # 生成示例电商库（玩具库，早期参考）
│   ├── load_olist.py      # 把 Olist 真实电商 CSV → data/olist.db（默认库）
│   ├── demos/             # 交互演示
│   │   ├── ask.py         #   自然语言 → SQL → 结果
│   │   ├── analyze.py     #   SQL → 沙箱 pandas 进阶分析
│   │   ├── chart.py       #   SQL → 沙箱 matplotlib 画图 → chart.png
│   │   ├── orchestrate.py #   多智能体编排：自主"取数→分析→审查→报告"
│   │   └── hello_bailian.py  #   百炼连通性自检（最早的 smoke test）
│   ├── spider/            # Spider 评测流水线
│   │   └── download / predict / score_spider.py
│   └── eval/              # 多智能体评测 + Langfuse 成本登记
│       └── run_agent_eval / critic_ab / langfuse_register_model.py
├── api/                   # FastAPI 服务（main.py：POST /ask、GET /health）
├── streamlit_app.py       # 网页 demo（输入问题 → 编排 → 报告 / 图表 / 轨迹）
├── docker-compose.yml     # 一键起 API 服务（挂 olist.db + 沙箱 DooD socket）
├── tests/                 # pytest（纠错 / 护栏 / EX / 沙箱 / 编排 / judge / schema / API）
├── sandbox/Dockerfile     # 沙箱镜像（python + pandas + matplotlib + 中文字体，非 root）
├── docs/                  # PROJECT-SPEC、面试速通清单
└── pyproject.toml
```
> 分层即包结构：`tools/`（能力）·`agents/`（生成+编排）·`eval/`（评测），顶层留 `config/paths/errors` 基建；各子包 `__init__.py` 收口公共 API（如 `from insight.agents import Text2SQLAgent`）。

---

## 🚀 快速开始

```bash
# 1. 依赖
uv sync

# 2. 配置百炼 API Key（环境变量；也可写进 .env）
#    Windows : setx DASHSCOPE_API_KEY "sk-xxxx"
#    macOS/Linux : export DASHSCOPE_API_KEY=sk-xxxx

# 3. 准备数据（默认用 Olist 真实电商数据；早期玩具库见 scripts/init_db.py）
#    先从 Kaggle 下 olistbr/brazilian-ecommerce 的 CSV 到 data/olist_csv/，然后：
uv run scripts/load_olist.py

# 4. 单 / 多 agent demo（示例问题按你的库自行替换）
uv run scripts/demos/ask.py "How many orders are there in total?"
uv run scripts/demos/orchestrate.py "每个订单状态各有多少订单？"

# 5. 沙箱画图 demo（需先构建沙箱镜像）
docker build -t insight-sandbox sandbox/      # 一次（含 pandas/matplotlib/中文字体）
uv run scripts/demos/orchestrate.py "把销售额最高的 5 个品类画成柱状图"

# 6. 网页 demo（Streamlit）
uv run streamlit run streamlit_app.py

# 7. 部署成服务（FastAPI + Docker Compose）
uv run uvicorn api.main:app --reload          # 本地 → http://localhost:8000/docs
docker compose up --build                     # 或容器化一键起（挂 olist.db + 沙箱 DooD）
```

> **可观测（可选）**：自托管 Langfuse（官方仓库 `docker compose up`），设好 `LANGFUSE_PUBLIC_KEY/SECRET_KEY/HOST` 后，所有 LLM 调用会自动上报到 `http://localhost:3000`。

## 📊 复现 Spider 评测

```bash
uv run scripts/spider/download_spider.py   # 下载偏难子集（99 题 / 20 库）
uv run scripts/spider/predict_spider.py    # 生成并冻结预测（调一次模型）
uv run scripts/spider/score_spider.py      # 计算 EX（不调模型，确定性）
```

## ✅ 测试

```bash
uv run pytest -q     # 47 passed（Docker 相关测试无环境时自动 skip）
```

---

## 🗺️ Roadmap

- [x] **Week 1** —— 单 Agent text2SQL + 只读执行 + 自我纠错 + 单元测试
- [x] Spider 基线 EX（生成/打分分离、确定性、诚实标注）
- [x] **Week 2** —— Langfuse 可观测 + Docker 沙箱 code execution（pandas + 画图）
- [x] **Week 3** —— 多智能体编排（LLM supervisor + agents-as-tools + Critic 闸门）+ 长链路归因
- [x] **Week 4** —— LLM-as-judge eval harness + Critic 有效性 A/B + 成本可观测 + Streamlit demo
- [x] **Week 5(A)** —— 真实电商数据（Olist）+ schema 上下文层（语义层 lite）+ FastAPI + Docker Compose 部署
- [ ] 长期 —— schema 检索 RAG（大库时）、反问澄清 / 多轮、MCP 多数据源、跨会话记忆

---

## 🔧 工程笔记（一些刻意的设计）

- **代码沙箱即安全边界**：LLM 生成的代码只在 Docker 容器里跑——`--network none` 断网、`--memory/--cpus/--pids-limit` 限资源、`--read-only` 不可写盘、非 root、`--rm` 即弃；**不向容器传任何 secret**。有"联网被挡"的测试背书。
- **数据怎么进沙箱、图怎么出沙箱**：容器读不到主机数据 → 把 SQL 结果序列化成 JSON 随代码注入、容器内还原成 `df`；图表则在沙箱里存成 PNG → base64 打印 → 主机解码——隔离与取数/取图两全。
- **一个自我纠错基类，两处复用**：SQL 与代码分析的纠错循环结构相同，抽出 `SelfCorrectingAgent` 基类，两个 agent 只填"建消息 / 怎么生成 / 怎么执行"三个钩子，循环只写一遍。
- **LLM supervisor 编排**：编排器用原生 function calling 把子 agent 当工具自主调度——`tool_calls` 决定调谁、结果 `role:"tool"` 喂回、无 `tool_calls` 即终答，`max_steps` 兜底防失控；工具出错也喂回让模型自纠。
- **Critic 闸门 = 系统级自我纠错**：终答前强制过 Critic 审忠实性（拿真实工具结果当证据），不通过把意见喂回重写、`max_reviews` 封顶；裁决用**强制 `tool_choice`** 拿结构化输出，比"求模型只输出 JSON"稳。
- **Workspace 黑板 + 鸭子类型**：子 agent 间的大数据（表/图）放共享 Workspace、回 LLM 只给摘要（省上下文）；编排器只依赖"有 `.review()`"接 Critic，不 import——可测、可替换。
- **可观测零侵入**：`llm.py` 一行换成 `langfuse.openai` 包装即自动 trace；agent `run()` 加 `@observe` 把一次调用归为一条层级 trace；测试侧关掉 tracing 保持与外部解耦。
- **异常分层即策略**：`SQLExecutionError`（可恢复）被 Agent 喂回重试；`DatabaseNotReadyError`（致命）抛到顶层——**用类型而非 if/else 决定处理**。
- **可复现评测**：模型只跑一次、预测落盘；改度量只需重新打分，不被重生成噪声污染。
- **LLM-as-judge 评多智能体**：报告质量没法用规则评，用"裁判模型"按 rubric（忠实性 / 相关性）打分；清楚其局限（裁判也会错、同源有偏差），只看相对趋势。
- **不信表面分、用 trace 定因**：Critic A/B 初看"忠实性↓2"，追 Langfuse trace 发现真因是**编排器钻牛角尖撞预算 + judge 把"没完成"误判为"不忠实"**（失败那次 Critic 根本没执行）——于是既修系统（预算降级 / 防钻牛角尖）又修测量，并诚实承认"玩具库上 base 已够忠实、Critic 增益不可测"。
- **真实数据 + 语义层 lite**：换上 Olist 真实电商数据（9 表 / 10 万订单）；`schema_context` 把业务口径注入 prompt——销售额=`SUM(order_items.price)`、客户用 `customer_unique_id`、品类葡→英 join 翻译表。**教训**：prompt hint 是软约束，**条件式("要英文才 join")模型常不理 → 改指令式("务必 join")才可靠**；真强约束要靠数据层语义层，"何时上 RAG / 何时上语义层"是工程判断（9 表不上 embedding-RAG = 避免过度工程）。
- **可部署服务 + 沙箱 DooD**：FastAPI 包成 REST（`/ask`、`/health`），重资源懒加载、编排器走依赖注入（测试可 override 成假编排器，不调真模型）；Docker Compose 一键起，挂宿主 `docker.sock` 让 API 容器调宿主 docker 跑沙箱（**Docker-out-of-Docker**）。**安全权衡**：挂 socket = 容器等同宿主 root，生产要换 rootless/gVisor/独立沙箱服务。
- **踩过的真实坑**：matplotlib 画中文要设 `font.sans-serif`（不是 `font.family`）且必须在画图前；seaborn `set_theme` 会重置字体（故改用 matplotlib 内置 `seaborn-v0_8` 风格）；Docker 镜像改了依赖/字体**必须 rebuild**。
- **CWD 无关路径**：所有路径锚定项目根（`Path(__file__).parents[...]`），从任意目录 / IDE 运行都不会找不到文件。

---

📄 完整设计文档：[docs/PROJECT-SPEC.md](docs/PROJECT-SPEC.md) · 仓库：<https://github.com/KaiyangDing/InsightProject>
