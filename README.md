# 新能源汽车产业技术情报知识图谱平台

按 [团队分工](docs/团队分工.md) 调整的五人协作开发基线。新版采用三个独立页面，旧六页演示保留在 `legacy/`，原 CSV 保留在 `data/legacy/`。

当前可运行：首页、三个页面入口、七表样例读取、问答返回结构。分析图表、12 意图问答、全量抽取和新 Schema 图谱导入由各负责人继续开发；骨架不代表这些功能已经完成。

## 快速开始

Python 3.10+，在仓库根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m eval.check_contracts
python -m streamlit run app.py
```

默认 `USE_SAMPLE=true`，无需 Neo4j 或大模型 API。已提交七个 Parquet 样例；重建执行 `python -m scripts.seed_sample`。样例为旧 CSV 的前 150 条专利；缺失字段及空表见 [运行说明](docs/run.md)。

## 目录与负责人

```text
app.py / requirements.txt          P1：应用壳与依赖
core/                             P1：配置、只读查询、七表加载
scripts/                          P1：抽取、建图、启动脚本
data/raw/ processed/ _sample/      P1：原始、全量、开发样例
data/results/                     P1：规模产物
pages/01_产业技术全景.py           P2
pages/02_创新主体与合作网络.py     P2
analysis/                         P2：统计与网络分析
pages/03_智能问答与关联路径.py     P3
qa/                               P3：问答引擎
docs/schema.md / run.md            P1
docs/qa_intents.md                 P3
docs/说明文档.md 答辩稿.md ppt/    P4
eval/ README.md delivery/          P5：评估与交付
legacy/ data/legacy/               旧演示与旧数据，只读保留
docs/legacy/                      旧说明与验证结果，仅作历史参考
```

## 开发分支

`main` 为稳定基线，`develop` 为联调分支。个人分支：`p1-data`、`p2-pages`、`p3-qa`、`p4-docs`、`p5-eval`，从同一公共基线创建。

```powershell
git fetch origin
git switch --track origin/p2-pages
# 完成自己负责的修改与验证后
git add pages/01_产业技术全景.py analysis/
git commit -m "feat: 完成产业技术全景"
git push
```

个人分支向 `develop` 提 PR，联调通过后 `develop` 向 `main` 提 PR。完整规则见 [协作指南](CONTRIBUTING.md)。

旧六页演示：配置 `.env` 的 Neo4j 凭据后，执行 `powershell -File scripts/start_legacy.ps1`。旧版仍依赖原有数据库，新 Schema 尚未导入，详见 [docs/run.md](docs/run.md)。
