# Insight · 自主数据分析 Agent —— 项目说明文档

> **Autonomous Data Analysis Agent** —— 给它一个数据库连接 + 一句自然语言业务问题，它能自主完成"探查 → 取数 → 跑数 → 反思 → 验证 → 成稿"的完整分析，产出带图表和归因论证的报告。

| 项目 | 内容 |
|---|---|
| 文档版本 | v0.1 (Draft) |
| 创建日期 | 2026-06-19 |
| 项目代号 | Insight（可改；候选：AutoAnalyst / DataSage） |
| 建议仓库名 | `insight-agent` |
| 负责人 | （你） |
| 状态 | 规划中，待启动 Week 1 |

---

## 1. 项目概述

### 1.1 一句话定义
一个**多智能体、可自主执行长链路分析、结论可溯源**的 AI 数据分析师。

### 1.2 电梯演讲
传统 BI 需要人写 SQL、看数、找原因。Insight 让用户直接用自然语言提业务问题（如"为什么上月华东区复购率下降了？"），系统自主规划分析路径、在沙箱里真实跑 SQL/Python、对中间结果反思和下钻、由 Critic 质检防止编数，最终产出一份**每个结论都能追溯到真实查询结果**的分析报告。

### 1.3 它不是什么（区别于 ChatBI）
| | 普通 ChatBI / text2SQL | Insight |
|---|---|---|
| 能力 | 把一句话翻译成一条 SQL | 自主规划**多步**分析、下钻、归因 |
| 执行 | 出 SQL 让人跑 | 沙箱内**真实执行** SQL + Python |
| 可靠性 | 不校验 | Critic 质检 + 结论强制溯源 |
| 产出 | 一张表/一个数 | 带论证链路的**分析报告** |
| 工程 | 调用即结束 | eval + 可观测 + 成本/可靠性体系 |

---

## 2. 背景与目标

### 2.1 问题背景
"用自然语言查数据/做分析"（ChatBI / DataAgent）是当前国内企业 AI 落地最热的方向之一，但多数产品停留在 text2SQL，缺少**自主多步分析**和**可靠性保障**。本项目用一个工程化、可评估的 agent 系统填补这个 gap。

### 2.2 项目目标

**技术目标**
- 构建一个生产级的多智能体数据分析系统。
- 端到端任务成功率相比单 agent 基线有可量化提升。
- 建立完整 eval 体系 + 可观测体系，支持回归测试驱动迭代。

**职业 / 简历目标**
- 集中展示四个硬核能力：**多智能体编排、长周期自主执行、深度工具使用与环境交互、生产级工程基建**。
- 产出可量化的简历指标（成功率、成本、步数）。
- 提供丰富的面试"现身说法"素材。

### 2.3 非目标（Out of Scope，防止范围蔓延）
- ❌ 不做通用聊天助手；只聚焦数据分析。
- ❌ v1–v4 不做权限/多租户/企业级账号体系。
- ❌ 不自己训练大模型（最多用 LoRA 做子任务路由，且为后期可选）。
- ❌ 不追求覆盖所有数据库方言；起步聚焦 SQLite/PostgreSQL。

---

## 3. 目标用户与使用场景

### 3.1 用户画像
- 数据分析师 / 运营 / 产品经理：有业务问题但不想/不会写复杂 SQL。
- 数据团队：想要一个能自动跑初步归因分析的助手。

### 3.2 核心使用场景（高光 Demo）
用户问：**"为什么上个月华东区的复购率比上上个月下降了？"**

```
1. 规划      → 拆解：确认"复购率"口径 → 确认下降是否真实显著 →
              按 渠道/品类/客群/价格 维度逐一下钻找主因
2. 探查schema→ 扫描表结构/字段/外键，定位订单表、用户表、地区维表
3. 取数      → 写 SQL，沙箱只读执行，确认复购率 32% → 27%（真降 5pct）
4. 下钻分析  → 多段 SQL + Python(pandas) 按维度拆解、做对比与相关性
5. 反思      → "某品类老客流失"嫌疑最大，但样本量够吗？有混淆变量吗？
6. 质检      → Critic 反事实校验：换口径再验，排除季节性
7. 成稿      → 报告：结论 + 图表 + 每步数据出处 + 论证链路
```

### 3.3 典型问题类型
- 描述性："上季度各品类销售额 Top 10？"
- 诊断性（核心）："为什么 X 指标下降了？"
- 对比性："A/B 两个渠道的用户 LTV 差异及原因？"
- 趋势性："过去 12 个月新客增长趋势及拐点？"

---

## 4. 系统架构

### 4.1 总体架构

```
                    ┌─────────────────────────────────────────┐
                    │        Orchestrator  (规划 / 调度)         │
                    │  任务拆解 · 子任务分派 · 预算控制 · 终止判定  │
                    └───────────────┬─────────────────────────┘
          ┌────────────────┬────────┼─────────────┬────────────────┐
          ▼                ▼                ▼              ▼
   ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐
   │ SQL / Code │   │  Analyst   │   │   Critic   │   │   Report   │
   │   Agent    │   │   Agent    │   │   Agent    │   │   Agent    │
   │  写&跑查询   │   │  解读结果   │   │ 质检/反事实 │   │   成稿      │
   └─────┬──────┘   └────────────┘   └────────────┘   └────────────┘
         │ tool calls
         ▼
   ┌──────────────────────────────────────────────────────────┐
   │   工具层 / 环境  (Tool & Environment Layer)                 │
   │  • 沙箱执行器 (SQL 只读 / Python-pandas, 超时&限额)          │
   │  • DB & 数仓连接器 (封装成 MCP server)                      │
   │  • 向量检索 (schema / 业务口径 / 历史分析记忆)               │
   │  • 图表渲染 · 文件产出                                       │
   └──────────────────────────────────────────────────────────┘
         │
         ▼
   ┌──────────────────────────────────────────────────────────┐
   │  横切基建 (Cross-cutting Infra)                            │
   │  Eval Harness  ·  Observability/Trace  ·  成本&模型路由     │
   │  ·  记忆 (短期 scratchpad + 长期业务知识)                    │
   └──────────────────────────────────────────────────────────┘
```

### 4.2 核心设计理念
1. **事实外置 + 结论可溯源**：模型负责推理，工具负责提供事实；报告里每个结论必须绑定一次真实查询结果。
2. **预算控制**：每个任务有步数预算与成本预算上限，防止死循环与成本失控。
3. **渐进式复杂度**：先单 agent 跑通拿基线，再拆多 agent —— 本身就是"单 vs 多 agent 对比"的好故事。
4. **可观测优先**：每一步 think / tool call / 成本 / token 全部 trace，可调试、可复盘。
5. **安全第一**：所有代码/SQL 在受限沙箱执行，最小权限。

### 4.3 单步执行循环（ReAct 变体）
```
plan → act(tool call) → observe(结果/报错) → reflect(够了吗?对吗?) → 继续 or 终止
```
报错会作为 observation 回灌，触发 agent 自我纠错（self-correction loop）。

---

## 5. 模块详细设计

### 5.1 Orchestrator（编排/调度）
- 职责：理解用户问题、拆解成子任务、分派给下游 agent、维护全局状态、控制预算、判定终止。
- 关键设计：用 LangGraph 状态机表达；关键控制流（终止条件、预算、Critic 回环）手写以显工程能力。

### 5.2 SQL / Code Agent（执行）
- 职责：根据子任务生成 SQL 或 Python，调用沙箱执行，读结果，必要时自我纠错重试。
- 关键设计：SQL 先经 AST 校验（只读、加 LIMIT）；执行报错回灌重试；低 temperature 保稳定。

### 5.3 Analyst Agent（解读）
- 职责：把查询结果转成业务洞察，决定是否需要进一步下钻。
- 关键设计：强制引用具体数据；输出结构化中间结论供 Critic 校验。

### 5.4 Critic Agent（质检）
- 职责：审查结论的逻辑/统计严谨性，做反事实校验（换口径、查样本量、找混淆变量），可打回重做。
- 关键设计：独立 prompt/角色；有"打回"权限但受回环次数上限约束。

### 5.5 Report Agent（成稿）
- 职责：汇总成最终报告：结论摘要 + 图表 + 论证链路 + 数据出处 + 局限说明。
- 输出：Markdown / HTML，含嵌入图表。

### 5.6 工具层 / 沙箱
- **SQL 执行器**：只读连接、statement timeout、强制 LIMIT、禁 DDL/DML、AST 校验。
- **Python 沙箱**：容器隔离 + Jupyter kernel，限 CPU/内存/时间，禁/限网络，临时文件系统。
- **Schema/口径检索**：向量库存 schema、字段说明、业务指标定义，按需检索（RAG）。
- **图表渲染**：matplotlib / plotly 出图。

### 5.7 记忆系统
- **短期**：本次任务的结构化 scratchpad（已知事实、已跑查询、中间结论）。
- **长期**：跨会话知识（业务口径、指标定义、历史分析），存向量库 + DB，可检索复用。

### 5.8 模型适配与路由（基于阿里云百炼 / DashScope）
- **接入方式**：百炼提供 OpenAI 兼容端点，直接用 `openai` SDK 指向 `https://dashscope.aliyuncs.com/compatible-mode/v1` + 环境变量 `DASHSCOPE_API_KEY` 即可；**一个 key 调通 chat / embedding / rerank**。
- **统一适配层**：在兼容端点之上再抽象一层 provider 接口，主用百炼，保留 base_url/key 切换位，未来可插拔 Claude/GPT（国内外通吃）。
- **模型路由档位**（型号以百炼控制台当前可用为准）：

  | 档位 | 用途 | 推荐模型 |
  |---|---|---|
  | 轻量 | 规划子步、摘要、分类、schema 格式化 | `qwen-flash` / `qwen3.5-flash` |
  | 主力 | 归因推理、复杂决策 | `qwen-plus` / `qwen3.5-plus` / `qwen3-max` |
  | 编码 | SQL / Python 生成（SQL-Code Agent 专用） | `qwen3-coder-plus` / `qwen3-coder-flash` |
  | 推理 | 最难的多步归因 | `qwen3` thinking 系列 / `deepseek-r1`（百炼托管） |

- **Embedding**：`text-embedding-v4`（维度可选 64–2048，默认 1024 平衡性价比；Qwen3-Embedding，100+ 语言）。
- **Rerank**：`gte-rerank`（百炼通用文本 rerank API，支持长文本/多语言）用于 RAG 精排。
- 路由策略 + 单平台多模型，本身是可量化降本的简历点。

---

## 6. 技术选型

| 层 | 选型 | 理由 |
|---|---|---|
| 语言 | Python 3.11+ | 对口已有经验、生态最全 |
| Agent 编排 | LangGraph（骨架）+ 关键控制流手写 | 自控 graph/state，避免黑盒，显功底 |
| 模型平台 | **阿里云百炼 / DashScope** | 已有账号/key；一个 key 调 chat+embedding+rerank，DeepSeek 也托管其上 |
| 主力模型 | Qwen3 系列（`qwen-plus`/`qwen3-max`）；SQL/代码用 `qwen3-coder-plus`；推理用 `qwen3` thinking / `deepseek-r1`（百炼托管） | 成本低、中文强、国内对口、按档位路由降本 |
| 模型适配 | `openai` SDK 指向 DashScope 兼容端点 + provider 抽象层 | 零摩擦接入，仍可插拔 Claude/GPT |
| 沙箱 | Docker + Jupyter kernel（Python）；只读连接（SQL） | 安全隔离 |
| 数据库 | SQLite（起步）/ PostgreSQL | 零成本起步，易扩展 |
| Embedding / Rerank | 百炼 `text-embedding-v4`（维度 64–2048，默认 1024）+ `gte-rerank` | RAG 向量化与精排，与主模型同平台同 key |
| 向量库 | pgvector / Qdrant | 存储与检索 schema/业务知识向量 |
| 工具协议 | MCP（封装数据源/工具为 server） | 跟进最新生态，面试加分 |
| Eval | 自建 harness + Spider / BIRD（CSpider 中文） | 拿客观基线分数 |
| 可观测 | Langfuse（开源） | trace/token/成本可视化 |
| Demo 前端 | Streamlit / Gradio | 面试演示 |
| 部署 | Docker Compose | 一键起，显工程完整度 |
| 依赖管理 | uv / poetry | 现代化、可复现 |

---

## 7. 数据与数据集

- **业务数据集（起步）**：公开电商数据集（如 Olist / Brazilian E-Commerce，或自造一套含订单/用户/商品/地区的库），数据直观、归因场景丰富。
- **SQL eval 数据集**：Spider / BIRD dev 子集（先取子集跑基线），中文可加 CSpider。
- **端到端 eval 数据集（自建）**：30–50 个真实分析任务，每个含问题 + 参考答案/评分 rubric。

---

## 8. Eval 评估体系（项目皇冠）

### 8.1 三层评估
- **L1 组件级**：SQL execution accuracy（Spider/BIRD EX）、工具调用成功率、生成 SQL 可执行率。
- **L2 端到端**：自建任务集，LLM-as-judge + 人工抽检，评任务成功率、归因正确率。
- **L3 回归**：每次改 prompt/架构跑全套 eval，看指标涨跌 —— 工程化铁证。

### 8.2 核心指标
| 指标 | 定义 |
|---|---|
| SQL 准确率 (EX) | 生成 SQL 执行结果与标准一致的比例 |
| 工具调用成功率 | 工具调用无报错完成的比例 |
| 端到端任务成功率 | 端到端任务达标（rubric/judge）的比例 |
| 归因正确率 | 诊断类任务找对主因的比例 |
| 平均步数 | 每任务平均 agent 步数（越低越高效） |
| 单任务成本 | 平均 token 成本（¥/任务） |
| 延迟 P50/P95 | 任务完成时间 |
| 幻觉率 | 结论中无查询结果支撑的比例（越低越好） |

### 8.3 回归流程
`改动 → 跑 eval harness → 对比指标 → 通过则合并`。所有指标进 Langfuse / 报表，形成迭代闭环。

---

## 9. 可观测性与运维
- **Tracing**：Langfuse 记录每个 agent step、prompt、tool call、token、成本、延迟。
- **成本监控**：按任务/模型聚合 token 与花费，支撑路由优化。
- **日志**：结构化日志 + 错误归类（SQL 错 / 工具错 / 模型错），便于调试。
- **可视化**：面试时直接打开 Langfuse 看一条完整执行链路。

---

## 10. 非功能性需求

| 维度 | 要求与手段 |
|---|---|
| **安全** | SQL 只读角色 + statement timeout + 强制 LIMIT + 禁 DDL/DML + AST 校验防注入；Python 容器隔离 + 资源限额 + 禁/限网络 + 临时 FS |
| **成本** | 任务级成本预算上限；模型路由；prompt caching；中间结果摘要压上下文 |
| **可靠性** | 工具报错自动重试（有上限）；模型降级；步数/回环预算防死循环；关键步幂等 |
| **性能** | 可并行的子查询并行执行；缓存重复查询；P95 目标后续设定 |
| **可维护** | 模块解耦、prompt 版本化、配置外置、测试覆盖 |

---

## 11. 开发路线图

| 阶段 | 目标 | 验收标准 |
|---|---|---|
| **Week 1** | 地基：单 agent text2SQL → 沙箱执行 → 回答；接公开数据集 | 跑通 Spider 子集，拿到**第一个基线 EX 分数** |
| **Week 2** | 加 code execution(pandas/画图) + 自我纠错循环；接 Langfuse | 能跑需要多步计算的题；trace 可视化 |
| **Week 3** | 多 agent 化（Orchestrator+SQL+Analyst+Critic+Report）；长链路归因 | 高光 demo 场景端到端跑通 |
| **Week 4** | eval harness 做扎实（端到端集+judge）；模型路由降本；Streamlit demo；写文档/博客 | 出对比报告：多 agent vs 单 agent 指标、成本下降数据 |
| **长期迭代** | MCP 多数据源、跨会话记忆、半自动 ETL、更多行业数据、LoRA 子任务路由 | 见附录 backlog |

---

## 12. 项目目录结构（建议）

```
insight-agent/
├── README.md
├── docs/
│   ├── PROJECT-SPEC.md                 # 本文档
│   ├── llm-fundamentals-cheatsheet.md  # 面试速通清单
│   └── architecture.md
├── pyproject.toml
├── .env.example
├── docker-compose.yml
├── src/insight/
│   ├── agents/        # orchestrator, sql_code, analyst, critic, reporter
│   ├── graph/         # LangGraph: state.py, workflow.py
│   ├── tools/         # sql_executor, python_sandbox, chart, schema_retriever
│   ├── memory/        # short_term, long_term
│   ├── llm/           # client(统一接口), router(模型路由)
│   ├── observability/ # tracing(langfuse)
│   ├── prompts/       # 版本化 prompt
│   └── config.py
├── eval/
│   ├── datasets/      # spider 子集 + 自建端到端集
│   ├── harness.py
│   ├── metrics.py
│   └── judges/        # LLM-as-judge
├── data/              # 示例数据库
├── app/               # streamlit demo
├── tests/
└── scripts/
```

---

## 13. 技能覆盖与面试映射

### 13.1 技能矩阵
| 项目模块 | 对应面试技能 |
|---|---|
| 多智能体编排 | Agent 架构、多智能体、控制流 |
| 沙箱代码执行 + 工具层 | tool use、function calling、环境交互、安全 |
| schema/口径向量检索 | RAG 全套 |
| 长链路上下文管理 | 上下文工程、KV cache 理解 |
| 模型路由降本 | 成本优化、tokenization、缓存原理 |
| Eval harness + Langfuse | 评估体系、可观测性（最稀缺加分项） |
| DeepSeek/Qwen + 可插拔 | 模型生态、国内对口 |

### 13.2 简历 bullet 模板（待填实测数字）
- 设计并实现多智能体自主数据分析系统，端到端任务成功率 **X%**，相比单 agent 基线提升 **Y%**。
- 自建 eval harness（SQL 准确率 + 归因质量），支持回归测试驱动迭代，覆盖 **N** 个任务。
- 通过模型路由 + 上下文工程，单任务成本降低 **Z%**、平均步数从 **A** 降到 **B**。
- 沙箱化工具执行 + Langfuse 全链路可观测，保障安全与可调试性。

### 13.3 面试可深聊
多 agent 控制流设计、长任务上下文管理、幻觉抑制（结论溯源）、eval 方法论、模型路由降本、SQL 安全沙箱。

---

## 14. 风险与对策

| 风险 | 对策 |
|---|---|
| 过度设计多 agent，迟迟跑不通 | v1 先单 agent，渐进拆分；每周有可演示产出 |
| Eval 设计耗时长 | 先用公开 benchmark 拿基线，端到端集逐步扩充 |
| 沙箱安全有坑 | 用成熟容器方案 + 最小权限，不自造轮子 |
| 成本失控 | 任务级预算上限 + 模型路由 + 缓存 |
| 模型 SQL 跑偏 | 低 temperature + schema 约束 + AST 校验 + 重试 |
| 范围蔓延 | 严守 §2.3 非目标，新想法进附录 backlog |

---

## 15. 术语表
- **ReAct**：Reason+Act，agent 推理与工具调用交替的范式。
- **EX (Execution Accuracy)**：SQL 按执行结果是否正确来评分。
- **LLM-as-judge**：用另一个 LLM 按 rubric 给开放式输出打分。
- **MCP**：Model Context Protocol，标准化工具/数据源接入协议。
- **KV Cache / Prompt Caching**：见 `llm-fundamentals-cheatsheet.md` 第 3 条。
- **MoE**：混合专家，稀疏激活的大模型架构。

---

## 附录 · 后续迭代 Backlog
- MCP 多数据源连接器（MySQL、ClickHouse、API）
- 跨会话长期记忆（记住业务口径/历史结论）
- 半自动 ETL / 数据清洗 agent
- 更多行业数据集（金融、SaaS）
- LoRA 微调一个小模型做子任务路由/分类，降本
- 多 agent 架构 A/B 对比实验报告
- 报告自动生成 PPT / 邮件推送
```
