# 环境、启动与迁移（P1）

Python 3.10+，在仓库根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m scripts.seed_sample
python -m eval.check_contracts
python -m eval.check_metrics
python -m eval.smoke_test
python -m streamlit run app.py
```

Copy-Item 仅在无 .env 时执行，保留已有本地配置。默认 USE_SAMPLE=true、QA_BACKEND=mock，不连接数据库 / 模型。不要自动加入旧 pylibs/，二进制扩展可能属于另一 Python 版本。修改 .env 后重启；NEO4J_* 优先，KG_NEO4J_* 为兼容名，默认无密码 / API 密钥。

## 样例边界

seed_sample 固定取旧 patents.csv 前 150 条，附带申请人、主 IPC、引用及共同申请关系。引用目标可在子集外，manifest.json 记录来源、选择与缺失项。

旧导出不能可靠恢复摘要、申请日期 / 年份、公开日期、专利类型、原始申请人、主体类型和第一申请人标志，字段留空。主题 / 功效两表仅有列定义，暂零行。公开国别从公开号前缀提取。此开发子集不能用于全量趋势或对外指标。

## 全量与新图谱（待 P1）

1. 原始导出放 data/raw/，不入 Git。
2. 实现 scripts/clean_data.py，从真实源字段输出七表到 data/processed/。
3. 实现 scripts/extract_entities.py 的主题 / 功效，完善日期与主体实体对齐。
4. 实现 scripts/build_graph.py，按 docs/schema.md 建图并输出真实 scale.json。
5. 设置 USE_SAMPLE=false，执行 python -m scripts.calculate_metrics，生成 data/results/ 下的两张全量结果表及清单。
6. 配置凭据，QA_BACKEND=real，重启并验证真实问答（待 P2 完成）。

这三个脚本目前明确退出提示待实现，不清库、不伪造成功。scale.json 在建图前 status=pending、规模为 null。全量目录为空会明确报错，不回退样例。这些是尚未完成的业务交付。

## 旧六页演示

旧 Schema 为 Company / Inventor / TechClass / Patent.id，与新契约不同，现有数据库没有修改。填入 .env 的真实 Neo4j 密码后：

```powershell
powershell -File scripts/start_legacy.ps1
```

原 ETL 与导入工具在 scripts/legacy/，从仓库根目录以模块方式运行。旧 ETL 从 data/raw/ 读取三个同名 Excel，输出 data/legacy/。旧导入器 `python -m scripts.legacy.load_neo4j` 会删除所连数据库全部节点，仅可针对可重建的旧演示库手动运行，不用于新 Schema。旧重载脚本也会修改数据库。

tools/neo4j-community-5.26.0/、Java 17 与本机数据库不入仓库。start_neo4j.ps1 只适用于自行准备该目录的机器，也可自行安装 Neo4j。旧验证工具移至 eval/legacy/，历史结果在 docs/legacy/，不代表新版验收。

## 两个独立开关与结果重建

- USE_SAMPLE=true：基础表读 data/_sample/，结果读 data/_sample/results/。
- USE_SAMPLE=false：基础表读 data/processed/，结果读 data/results/，缺文件明确报错。
- QA_BACKEND=mock：三个固定示例返回明确标注的假数据，页面显示演示提示。
- QA_BACKEND=real：调用真实问答实现；当前仍待 P2 完成，返回失败，不会回退假数据。

seed_sample 同时生成样例结果；仅重算当前模式结果执行 `python -m scripts.calculate_metrics`。新配置重启后生效。样例与全量结果必须有 scope 一致的 metrics_manifest.json，加载器拒绝混用。主题年度表当前因缺可靠源字段而为空，不能为了画图伪造年份 / 主题。

预计算指标口径见 schema.md；界面职责与数字格式见 ui_spec.md；问答返回图和实体字段见 qa_intents.md。P1 提供数据与指标，P2 完成真实问答，P3 统一页面与简单聚合。
