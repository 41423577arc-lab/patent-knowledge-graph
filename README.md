# 新能源汽车产业技术情报知识图谱平台

面向新能源汽车专利数据的产业技术情报分析平台，基于结构化专利数据与知识图谱，提供产业技术全景、创新主体与合作网络分析，以及自然语言智能问答。

项目按新版 [团队分工](docs/团队分工.md) 协作：P1 数据与预计算指标，P2 问答服务，P3 前端，P4 文档，P5 质量与交付。

## 当前实现状态

| 模块 | 当前状态 | 说明 |
| --- | --- | --- |
| P1 数据与图谱 | 已提供样例与全量数据交付 | 七张基础契约表、两张预计算结果表；包含 481 件真实专利样例和 106,393 件全量数据及对应指标文件 |
| P2 智能问答 | **12 类正式意图已实现** | 规则问答、可选 DeepSeek 增强、实体链接、只读图谱检索、证据子图、结论生成与异常降级 |
| P3 前端 | 三页 Streamlit UI | 产业技术全景、创新主体与合作网络、智能问答与关联路径 |
| P4 项目文档 | 持续整理 | Schema、运行说明、问答意图契约及问答后端交付说明已提供 |
| P5 质量与交付 | 开发验证已完成部分 | P2 样例回归和开发集验证已有记录；团队集成、全量图谱复验及正式独立验收仍需完成 |

**重要区分：** `QA_BACKEND=mock` 是页面开发用的三个假数据示例；`QA_BACKEND=real` 才会调用真实问答后端。真实问答代码已实现，不代表任意环境已经连通 Neo4j，也不代表全量图谱端到端验收已经完成。

## 功能概览

### 三个应用页面

1. **产业技术全景**：展示新能源汽车产业技术数据与指标。
2. **创新主体与合作网络**：查看创新主体及合作关系。
3. **智能问答与关联路径**：输入自然语言问题，查看问答结论、结果数据、关联路径、实体候选和查询解释。

### 12 类智能问答

| 编号 | 意图 | 可回答的问题 |
| --- | --- | --- |
| CQ01 | `Q_TOP_APPLICANTS` | 创新主体专利申请量排名 |
| CQ02 | `Q_INFLUENTIAL_APPLICANTS` | 引证网络主体影响力排名（被引次数、PageRank、度中心性、中介中心性） |
| CQ03 | `Q_COMPANY_IPC` | 指定主体的 IPC 技术领域布局 |
| CQ04 | `Q_COOPERATION` | 指定主体的共同申请与合作伙伴 |
| CQ05 | `Q_TOPIC_TREND` | 指定技术主题的年度申请趋势 |
| CQ06 | `Q_GROWTH_TOPICS` | 技术主题增长情况与增长率 |
| CQ07 | `Q_COMPANY_TOPICS_DOMAIN` | 指定主体涉及的技术主题和领域 |
| CQ08 | `Q_COOP_LAYOUT` | 合作主体各自的技术布局 |
| CQ09 | `Q_CITATION_APPLICANTS` | 指定主体引用了哪些主体的专利 |
| CQ10 | `Q_DEPENDENCY_EXPOSURE` | 外部引证主体集中度与依赖暴露度 |
| CQ11 | `Q_COMPANY_PATENTS` | 指定主体的代表性专利 |
| CQ12 | `Q_TOPIC_APPLICANTS` | 指定技术主题的主要创新主体 |

### 问答处理流程

1. **问题预检**：检查问题是否属于专利数据范围，并识别缺少指标、时间或实体等需要澄清的条件。
2. **意图与槽位识别**：规则解析或可选 LLM 识别 12 类意图及主体、主题、年份、排名数量和指标等参数，并进行白名单校验。
3. **实体链接**：优先使用标准名称、原始名称和已确认别名；模糊匹配只提供候选，不会静默合并有歧义的实体。
4. **证据检索**：通过固定的参数化只读 Cypher 查询 Neo4j，并按需读取 P1 基础表和预计算指标。
5. **结果组织**：返回结构化数据、可追溯的证据子图和中文结论。LLM 仅辅助意图识别或组织已检索事实；模型不可用或输出校验失败时降级为规则结果。
6. **统一接口**：前端通过 `qa.service.answer(question, mode="auto")` 调用，返回 `ok`、`intent`、`slots`、`entities`、`data`、`graph`、`conclusion`、`cypher`、`mode`、`error` 和 `suggestions` 等字段。

完整意图定义、槽位约束、数据口径和边界处理见 [问答意图与接口说明](docs/qa_intents.md)；模块实现和测试记录见 [P2 问答后端交付说明](qa/交付说明.md)。

## 数据范围与已知限制

- 数据按 `USE_SAMPLE` 选择样例或全量范围，基础表和预计算结果必须与 Neo4j 实例保持同一范围，不可混用。
- 481 件真实样例图谱已验证全部 12 类问答。全量 106,393 件数据的正式预计算结果中，CQ02、CQ05、CQ06 已完成对应结果验证；其余 9 类依赖图谱的意图仍需在匹配的全量 Neo4j 环境完成端到端复验。
- 2024–2025 年数据不完整，技术主题趋势与增长分析截至最近完整年份 2023；明确查询不完整年份时会提示数据覆盖限制。
- 当前数据不含销量、营收、市值等商业指标；也没有经过核验的整车制造商分类，因此不能据此回答商业排名或车企专属排名。
- 引证关系仅作为技术知识关联与依赖暴露的代理指标，不代表真实采购关系或供应链依赖。CQ10 同时展示外部主体映射覆盖率，解释时应保留这一限制。
- 开发集成绩不等同于 P5 正式独立验收。旧版 `eval/smoke_test.py` 仍有“待 P2 实现”的历史断言，需要在团队集成时由 P5 同步更新。

## 启动

要求 Python 3.10+。在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# 仅在没有 .env 时复制
Copy-Item .env.example .env
python -m eval.check_contracts
python -m streamlit run app.py
```

默认配置为 `USE_SAMPLE=true`、`QA_BACKEND=mock`。该模式不需要 Neo4j 或模型 API，页面三提供三个带“演示：”前缀的假数据示例，仅用于检查页面展示。

### 启用真实问答

在 `.env` 中设置与当前数据范围一致的配置，并启动对应的 Neo4j 实例：

```dotenv
USE_SAMPLE=true
QA_BACKEND=real
NEO4J_URI=bolt://127.0.0.1:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=你的数据库密码
QUERY_TIMEOUT=10
```

- 样例环境使用 `USE_SAMPLE=true`，并连接导入了 481 件样例数据的 Neo4j。
- 全量环境使用 `USE_SAMPLE=false`，将 `DATA_DIR` 指向包含全量 `processed/`、`results/` 的数据目录，并连接同范围的全量 Neo4j。
- LLM 是可选增强。配置 DeepSeek 时可增加 `LLM_API_BASE=https://api.deepseek.com`、`LLM_MODEL=deepseek-flash` 和 `LLM_API_KEY`。不配置 Key 时，真实问答仍可使用规则模式。
- 接口支持请求模式 `auto`、`rule`、`llm`；响应中的 `mode` 表示实际执行模式，模型不可用时可能自动降级为 `rule`。

## 目录结构与职责

```text
core/                 配置、数据读取、Neo4j 连接
scripts/              样例准备、数据处理与指标计算脚本
data/_sample/         481 件样例基础表及预计算结果
data/processed/       本地全量基础表
data/results/         本地全量预计算结果
qa/                   P2 问答服务、意图、实体链接、检索、证据图与测试
pages/                三个 Streamlit 业务页面
ui/                   统一主题与展示组件
analysis/              前端取数与分析辅助
docs/schema.md        图谱 Schema
docs/run.md           数据与系统运行说明
docs/qa_intents.md    12 类问答意图与接口契约
qa/交付说明.md        P2 后端架构、数据口径、测试与待办
eval/                 契约、指标和应用检查
legacy/               保留的旧版演示代码
```

样例数据重建：`python -m scripts.seed_sample`；单独重算指标：`python -m scripts.calculate_metrics`。执行前请确认对应的数据目录和输入文件。

## 开发验证

P2 交付说明记录了以下开发验证结果：问答后端回归 27/27；冻结开发集包含 60 道可答题和 12 道边界题，规则模式与请求 LLM 模式均通过 72/72。LLM 请求模式中有部分题目通过规则降级完成。这些是开发验证记录，不是 P5 正式独立验收结论。

可运行基础检查：

```powershell
python -m compileall -q qa
python -m unittest discover -s qa/tests -v
python -m eval.check_contracts
python -m eval.check_metrics
```

## 分支与协作

- `main`：稳定基线；`develop`：团队联调。
- `p1-data`、`p2-qa`、`p3-frontend`、`p4-docs`、`p5-eval`：新版个人开发分支。
- `p2-pages`、`p3-qa`：旧分工分支，保留历史，不再作为新任务入口。

个人分支向 `develop` 提交 PR，联调后由 `develop` 向 `main` 提交 PR。目录边界、旧分支迁移及验证命令见 [CONTRIBUTING.md](CONTRIBUTING.md)。

旧六页演示保留：配置真实数据库凭据后执行 `powershell -File scripts/start_legacy.ps1`。详情见 [运行说明](docs/run.md)。
