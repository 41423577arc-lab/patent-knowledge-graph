# P1 交接说明（数据、图谱、口径）

> 更新：2026-11-25。配套：[schema.md](schema.md)、[run.md](run.md)、[data_profile.md](data_profile.md)、[page_metrics.md](page_metrics.md)。
> 一句话：七张全量表、481 件样例、Neo4j 全量契约图、展示层别名/企业级引用、100 条人工核对结果都已就绪；页面口径按 [page_metrics.md](page_metrics.md) 执行。

## 0. 当前状态

| 项目 | 状态 |
|---|---|
| 七张契约表 | 已生成，`eval.check_contracts` 34/34 通过 |
| `USE_SAMPLE=true` | 481 件真实样例，页面可直接跑 |
| `USE_SAMPLE=false` | 106,393 件全量七表可读 |
| Neo4j | Desktop 本地实例 2026.10.2，147,174 节点 / 571,663 关系 |
| 图谱校验 | 节点/关系计数与 parquet 逐项一致 |
| 页面冒烟 | `eval.smoke_test` 4 个入口全过 |
| 预计算指标 | 样例 366 家 / 295 行；全量 27,557 家 / 1,293 行；`load_result` 可读 |
| 企业别名 | 393 条，展示层；契约表未改 |
| 企业级引用 | 135,007 个主体对；口径 C 聚合 |
| 人工抽样 | 100 条核对结果，标签已填 |

## 1. 数据入口

```python
from core.data_loader import load_table, available_tables
patents = load_table("patents")
```

- `USE_SAMPLE=true` → `data/_sample/`（481 件，开发/演示）
- `USE_SAMPLE=false` → `data/processed/`（全量）
- 缺目录/缺表会明确报错，不静默回退。
- 七表列名/顺序不可改；需要额外字段放 Neo4j 属性或 `data/results/` 辅助表。

```python
from core.database import run_query, health_check
rows = run_query("MATCH (p:Patent) RETURN count(p) AS n")
```

- 只接受可信、参数化的只读 Cypher；不要让大模型生成 Cypher。
- 连接信息在 `.env`：`NEO4J_URI=neo4j://127.0.0.1:7687`、`NEO4J_USER=neo4j`、`NEO4J_PASSWORD`。
- Neo4j Desktop 实例必须先 Start。

## 2. 文件清单

### 契约 C 七表（`data/processed/`）

| 表 | 行数 | 用途 |
|---|---:|---|
| `patents.parquet` | 106,393 | 专利主表；全部专利口径 |
| `applicants.parquet` | 115,927 | 专利-申请人关系；27,557 个标准化主体 |
| `patent_ipc.parquet` | 306,023 | 专利-IPC；13,166 个 IPC |
| `patent_topic.parquet` | 104,723 | 专利-主题；50 主题、8 领域 |
| `patent_efficacy.parquet` | 391,642 | 专利-功效 |
| `citations.parquet` | 442,917 | 引用边；样本内 35,114、外部 407,803 |
| `cooperation.parquet` | 9,826 | 共同申请；6,704 件多申请人专利 |

### 辅助表（`data/results/`，非契约 C）

| 文件 | 规模 | 用途 |
|---|---:|---|
| `external_citation_applicants.parquet` | 46,539 行 | 外部引用主体明细；CQ09/CQ10 精确外部边 |
| `company_alias.csv` | 393 条 | 企业别名 → 规范名；P3 实体链接、P2 展示 |
| `cooperation_merged.parquet` | 9,750 条 | 展示层合作网络；P2/P3 优先用 |
| `company_patent_counts.csv` | 27,190 企业 | 展示层企业专利数；P2 排行 |
| `company_citation_pairs.parquet` | 135,007 对 | 主体级引用聚合（口径 C）；快速展示 |
| `company_citation_summary.json` | — | H1 覆盖、Top 主体对 |
| `manual_sample_100.csv` | 100 行 | 人工抽样核对结果；标签已填 |
| `manual_sample_100.md` | — | 抽样、标注结果与 P/R/F1 说明 |
| `topic_quality.csv` | 50 主题 | 主题计数、`（未细分）` 标记 |
| `company_metrics.parquet` | 样例 366 / 全量 27,557 行 | P2/P3 预计算企业指标；`load_result` 读取 |
| `topic_year.parquet` | 样例 295 / 全量 1,293 行 | 主题×年度计数；P2 页面一、P3 趋势 |
| `metrics_manifest.json` | — | 结果 scope、行数、SHA-256；样例/全量各一份 |
| `data_quality.json` | — | 规模、覆盖、缺失、16 批次、已知问题 |
| `scale.json` | — | 图谱计数 + P1-8 统计；`status=done`、`graph_status=ok` |
| `contract_check.json` | — | 34 项结构校验 |

### 图谱（Neo4j）

5 类节点：Patent 106,393、Applicant 27,557、IPC 13,166、Technology 50、Domain 8。
6 类关系：APPLIES_FOR 115,927、CITES 35,114、HAS_IPC 306,023、INVOLVES 104,723、BELONGS_TO 50、CO_APPLIED_WITH 9,826。

## 3. 给 P2（页面一、二）

- 页面一用 `load_table("patents")` + `patent_ipc` + `patent_topic` + `patent_efficacy`；**不要**用 `company_patent_counts` 算专利总量。
- 专利总量/类型/国别：**106,393**。
- 技术图（IPC/主题/功效）：**86,814** 技术类；标题注“占技术类专利”。
- 主题年度表：`load_result("topic_year")`（样例 295 行 / 全量 1,293 行），不要自己从 `patent_topic` 重算。
- 企业排行：`company_patent_counts.csv`（展示层合并），不要直接改契约 `applicants`。
- 企业指标：`load_result("company_metrics")`（样例 366 家 / 全量 27,557 家），含 `patent_count`、`cited_count`、`pagerank`、`degree`、`betweenness`；前端不要重算中心性。
- 合作网络：`cooperation_merged.parquet`（9,750 条），标题注“展示层合并，契约表未改”。
- 影响力/PageRank：`company_metrics` 基于样本内 CITES 的申请人引用图，无外部占位节点；标题必须写“样本内引用网络”，不能写“全产业影响力”。
- 企业技术布局：用 `HAS_IPC` / `INVOLVES`，外观设计没有技术属性。
- 年趋势：2010/2015—2023；2024—2025 标“不完整”。
- 申请人类型空值显示“未知”；“境外/未知”保持原样。
- 完整口径见 [page_metrics.md](page_metrics.md) 第 3—4 节。

## 4. 给 P3（页面三、问答）

- 入口契约不变：`answer(question, mode="auto")`，返回 `ok/intent/slots/entities/data/graph/conclusion/cypher/mode/error/suggestions`。
- 意图列表见 [qa_intents.md](qa_intents.md)；每个意图用预置参数化 Cypher，不要让 LLM 生成 Cypher。
- 实体链接：`company_alias.csv` 先精确匹配 alias → canonical；再对 `Applicant.name` 做近似匹配；多候选要返回候选，不擅自选。
- `Q_COOPERATION` / `Q_COOP_LAYOUT`：优先读 `cooperation_merged.parquet`；Kia 与 Hyundai 不合并，`中国南方` 是 `pending_review`。
- `Q_INFLUENTIAL_APPLICANTS`：只能称“样本内引用网络”指标。
- `Q_CITATION_APPLICANTS`：图内 CITES 只有样本内；外部被引主体用 `external_citation_applicants.parquet`。
- `Q_DEPENDENCY_EXPOSURE`（CQ10）：优先用 `external_citation_applicants` 明细计算 `c(A,B)/C_A`，`C_A<30` 不做依赖判断；`company_citation_pairs` 的 `citing_patent_count` 是“引用广度”，不是引用次数。完整方法见 [page_metrics.md](page_metrics.md) 第 6 节。
- 所有答案标：数据口径（全部/技术类）、时间窗口、引用覆盖率、样本量；无数据就直说。
- 大模型只做意图/语言，不接触 Cypher；无 API 时走规则模板，页面标“规则模式”。

## 5. 给 P4（文档/答辩）

可直接使用的事实：

- 原始 16 个 xlsx 合并为 142,112 行 × 204 列；按申请号去重为 106,393 件，删除 35,719 行。
- 专利类型：发明授权 42,678、实用新型 24,511、发明申请 19,625、外观设计 19,579。
- 技术覆盖：IPC 99.0%、主题 82.35%、功效 89.41%（分母 86,814 非外观设计）。
- 引用：442,917 条；样本内 7.93%，外部主体覆盖 3.90%。
- 图谱：147,174 节点 / 571,663 关系；CITES 仅样本内 35,114。
- 企业别名 393 条、合作边 9,750、企业级引用 135,007 主体对。
- 16 批次：1,008 行样本显示 14 个批次全“授权”、2 个全“驳回”；不是随机全量。
- 2024—2025 不完整：2024 申请 6,519、2025 申请 236；趋势窗口用 2010/2015—2023。
- 局限：引用是技术依赖的代理指标；别名不是完整实体消解；主题是规则抽取；外观设计无技术属性；申请人国家字段缺失。

## 6. 给 P5（质量/交付）

- 结构校验：`data/results/contract_check.json`，34/34 通过；8 个数据缺失警告。
- 规模/质量：`data/results/scale.json`、`data_quality.json`。
- 抽样：`manual_sample_100.csv` 100 条，标签列 `label_*` 已填；按 `manual_sample_100.md` 直接引用准确率与 P/R/F1 结果，不重复计算。
- 别名：`company_alias.csv` + `alias_summary.json`；H1：`company_citation_pairs.parquet` + `company_citation_summary.json`。
- 主题：`topic_quality.csv`；`（未细分）` 单列。
- 一致性：`eval.check_contracts`、`eval.smoke_test` 均可复跑。
- 注意：100 条抽样已完成标注与 P/R/F1 统计；结果见 `manual_sample_100.md`。

## 7. 不能回答 / 不能宣称

- 不能称“全产业全量”：16 个批次按法律状态分层导出，不是随机全量。
- 不能做 2024—2025 趋势结论：数据不完整。
- 不能把 CITES 当完整引用网络：只导入样本内 35,114 条；外部主体覆盖 3.90%。
- 不能把企业级引用当精确依赖边：`cited_applicants` 是平铺列表，`company_citation_pairs` 是聚合。
- 不能把别名合并当完整实体消解：393 条只是展示层，集团子公司差异被隐藏。
- 不能把主题当标准分类：规则词典，82.35% 覆盖，`（未细分）` 是 IPC 兜底。
- 不能给申请人国家：七表没有该字段，`Applicant.country` 为空。
- 不能把外观设计算进技术分析：无 IPC/主题/功效。

## 8. 复现命令

```powershell
cd "g:\大学\课程\知识图谱\patent-knowledge-graph"
.\.venv\Scripts\Activate.ps1

python -m scripts.clean_data
python -m scripts.extract_entities
python -m scripts.build_relations
python -m scripts.validate_tables

python -m scripts.seed_sample
python -m scripts.build_graph --reset
python -m scripts.build_company_alias
python -m scripts.build_company_citations
python -m scripts.build_quality_report

python -m eval.check_contracts
python -m eval.smoke_test
python -m streamlit run app.py
```

`build_graph` 需要 Neo4j Desktop 实例已 Start；`--reset` 会清空契约标签后重建。全量清洗读取 466 MB xlsx，约 5 分钟；建图约 2 分钟。

## 9. 验收状态

- 七表结构：PASS（34/34）
- 图谱计数：与 parquet 一致
- 页面骨架：4 个入口 smoke PASS
- P1-8 产物：已生成并在 `交付给同伴的内容/P1-8_质量与别名/`
- 文档：`schema.md`、`run.md`、`data_profile.md`、`page_metrics.md`、本文件
