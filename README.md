# 新能源汽车产业技术情报知识图谱平台

按新版 [团队分工](docs/团队分工.md) 建立的五人开发基线：P1 数据与预计算指标，P2 问答服务，P3 全部前端，P4 文档，P5 质量与交付。

当前提供三页公共 UI、七张真实来源样例表、两张预计算结果表，以及三个明确标注为假数据的问答演示。全量清洗、新 Schema 建图、真实 12 意图问答和完整业务交互仍由负责人继续开发。

## 启动

Python 3.10+，在仓库根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# 仅在没有 .env 时复制
Copy-Item .env.example .env
python -m eval.check_contracts
python -m streamlit run app.py
```

默认 `USE_SAMPLE=true`、`QA_BACKEND=mock`，不需要 Neo4j 或模型 API。页面三可选择三个“演示：”示例，所有结论都标注“演示假数据”。假数据不能用于课程指标或准确率评估。

## 目录与负责人

```text
requirements.txt / core/ / scripts/   P1：数据、图谱、取数与指标计算
 data/_sample/                        P1：七表开发子集
 data/_sample/results/                P1：样例指标与主题年度表
 data/processed/ / data/results/      P1：本地全量表与全量结果
qa/                                  P2：问答引擎，唯一入口 qa.service.answer
app.py / pages/ / ui/                 P3：首页、三个页面与统一视觉
analysis/page_data.py                 P3：页面取数、筛选、简单聚合
 docs/schema.md / run.md              P1
 docs/qa_intents.md                   P2
 docs/ui_spec.md                      P3
 docs/说明文档.md 答辩稿.md ppt/      P4
 eval/ / README.md / delivery/        P5
legacy/ data/legacy/ docs/legacy/      保留的旧演示、旧 CSV 与历史说明
```

基础表与预计算结果都随 USE_SAMPLE 切换，不回退、不混用。重建样例执行 `python -m scripts.seed_sample`，单独重算指标执行 `python -m scripts.calculate_metrics`。主题年度表当前为空，因为旧样例没有可靠申请年与主题；不能用零值或虚构年份补齐。

## 分支

- `main`：稳定基线；`develop`：联调。
- `p1-data`、`p2-qa`、`p3-frontend`、`p4-docs`、`p5-eval`：新版个人分支。
- `p2-pages`、`p3-qa`：旧分工分支，保留历史，不再作为新任务入口。

```powershell
git fetch origin
git switch --track origin/p3-frontend
# 修改自己负责的文件并验证
git add app.py pages/ ui/ analysis/ docs/ui_spec.md
git commit -m "feat: 完善统一页面"
git push
```

个人分支向 develop 提 PR，联调后 develop 向 main 提 PR。目录边界、旧分支迁移及验证命令见 [CONTRIBUTING.md](CONTRIBUTING.md)。

旧六页演示保留：设置真实数据库凭据后执行 `powershell -File scripts/start_legacy.ps1`。详情见 [运行说明](docs/run.md)。
