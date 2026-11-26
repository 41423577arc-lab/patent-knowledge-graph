# 环境、启动与迁移（P1）

> 交接说明见 [handoff.md](handoff.md)，页面口径见 [page_metrics.md](page_metrics.md)。

Python 3.10+，在仓库根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m scripts.seed_sample
python -m eval.check_contracts
python -m eval.smoke_test
python -m streamlit run app.py
```

Copy-Item 仅在无 .env 时执行，保留已有本地配置。默认样例模式不连接数据库 / 模型。不要自动加入旧 pylibs/，二进制扩展可能属于另一 Python 版本。修改 .env 后重启；NEO4J_* 优先，KG_NEO4J_* 为兼容名，默认无密码 / API 密钥。

## 样例边界

`python -m scripts.seed_sample` 从 `data/processed/` 的七张全量表重建 `data/_sample/`：400 件按专利类型 / 主主题领域 / 申请年段分层抽样，再加 50 件基础集引用最多的专利和 31 件二跳引用专利，共 **481 件**。七表按同一 `patent_id` 过滤；`cooperation` 由样例内申请人重新配对生成。选择明细见 `data/results/sample_selection.csv`，统计见 `data/_sample/manifest.json`。

样例字段完整：摘要缺失 6 件、申请日缺失 3 件，主题 / 功效不再为空。非外观设计 IPC 覆盖 99.5%、主题 85.7%、功效 90.2%；样本内引用边 82 条。引用目标可在子集外，`cited_in_sample` 已按样例重新计算。

这是**开发样例**，不是统计抽样：引用闭包故意多选被引专利，专利类型比例也偏离全量。不能用于对外规模 / 趋势结论；全量数字看 `data/results/scale.json` 和 `docs/data_profile.md`。

## 全量七表与 Neo4j

1. 原始导出放 `data/raw/原始专利汇总.xlsx`，不入 Git。
2. `python -m scripts.clean_data` 生成 `patents` / `applicants`。
3. `python -m scripts.extract_entities` 生成 `patent_ipc` / `patent_topic` / `patent_efficacy`。
4. `python -m scripts.build_relations` 生成 `citations` / `cooperation`。
5. `python -m scripts.validate_tables` 做七表契约校验（`USE_SAMPLE=false`）。
6. 启动 Neo4j Desktop 本地实例，配置 `.env` 的 `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD`。
7. `python -m scripts.build_graph` 按 `docs/schema.md` 建图并写 `data/results/scale.json`；节点/关系计数与 parquet 不一致会失败。
8. `USE_SAMPLE=false`，重启验证图查询。
9. `python -m scripts.build_company_alias` 生成展示层别名、合并合作边、企业专利数。
10. `python -m scripts.build_company_citations` 生成企业级引用聚合（口径 C）。
11. `python -m scripts.build_quality_report` 生成/更新 `scale.json`、`data_quality.json`、`manual_sample_100.csv`、`topic_quality.csv`。
12. `python -m scripts.calculate_metrics` 生成当前 `USE_SAMPLE` 范围的 `company_metrics.parquet`、`topic_year.parquet`、`metrics_manifest.json`；全量再执行 `USE_SAMPLE=false python -m scripts.calculate_metrics`。

`data/processed/` 为空时 `load_table` 会明确报错，不回退样例。全量图已导入：Patent 106,393、Applicant 27,557、IPC 13,166、Technology 50、Domain 8；六类关系共 571,663 条（Neo4j 2026.10.2，Desktop 本地实例）。

### 辅助表（P1-8，展示层）

- `data/results/company_alias.csv`、`cooperation_merged.parquet`、`company_patent_counts.csv`：别名与企业级合作；契约表不改。
- `data/results/company_citation_pairs.parquet`、`company_citation_summary.json`：企业级引用聚合；不是精确专利边。
- `data/results/manual_sample_100.csv`：100 条人工核对框，标签列待 P5 填；`topic_quality.csv` 标出 `（未细分）`。
- `data/results/data_quality.json`：规模、覆盖、缺失、16 批次、已知问题；`scale.json` 同时保留图谱计数和 P1-8 统计。

### 预计算指标（页面一/二）

- 样例：`data/_sample/results/company_metrics.parquet`、`topic_year.parquet`、`metrics_manifest.json`。
- 全量：`data/results/company_metrics.parquet`、`topic_year.parquet`、`metrics_manifest.json`。
- 读取：`core.data_loader.load_result("company_metrics" / "topic_year")`；按 `USE_SAMPLE` 切换，校验 scope、行数、SHA-256，不跨范围回退。
- 重算：`python -m scripts.calculate_metrics`；全量加 `USE_SAMPLE=false`。计算依赖 `networkx` + `scipy`。

### Neo4j Desktop 注意

本机用 Neo4j Desktop 管理本地实例，数据目录通过用户环境变量 `NEO4J_DESKTOP_DATA_PATH=D:\Neo4jData` 指到 D 盘。实例启动后，在 **Details** 里确认 Bolt 地址和端口，并保证与 `.env` 的 `NEO4J_URI` 一致。重跑导入时加 `--reset`，否则非空图会拒绝重复建边。外部引用 407,803 条不建占位节点，企业级分析用 `external_citation_applicants.parquet`。

## 旧数据

`data/legacy/` 是旧 CSV 存档，不再参与样例生成；`data/_sample/` 已改为从 `data/processed/` 重建。旧六页演示、旧 ETL 与旧验证工具已移除。
