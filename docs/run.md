# 环境、启动与迁移（P1）

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
6. `python -m scripts.build_graph` 按 `docs/schema.md` 建图并写 `data/results/scale.json`（P1-7，待执行）。
7. 配置凭据，`USE_SAMPLE=false`，重启验证。

`data/processed/` 为空时 `load_table` 会明确报错，不回退样例。Neo4j 未建好前，`USE_SAMPLE=false` 只能读表，不能完成图查询。

## 旧数据

`data/legacy/` 是旧 CSV 存档，不再参与样例生成；`data/_sample/` 已改为从 `data/processed/` 重建。旧六页演示、旧 ETL 与旧验证工具已移除。
