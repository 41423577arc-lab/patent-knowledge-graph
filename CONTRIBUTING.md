# 团队协作与分支规则

依据新版 [团队分工](docs/团队分工.md)。本仓库已启用 Git；T0 / D1 / D2 为相对里程碑，由团队确定具体日期。

| 分支 | 角色 | 修改范围 |
|---|---|---|
| main | 稳定版本 | 接收通过联调的 develop |
| develop | 集成联调 | 接收个人分支 PR |
| p1-data | P1 数据与图谱 | requirements.txt、core/、scripts/、data/、.env.example、docs/schema.md、docs/run.md |
| p2-qa | P2 问答服务 | qa/、docs/qa_intents.md |
| p3-frontend | P3 全部前端 | app.py、pages/、ui/、analysis/、docs/ui_spec.md |
| p4-docs | P4 文档与汇报 | docs/说明文档.md、docs/答辩稿.md、docs/ppt/ |
| p5-eval | P5 质量与交付 | eval/、README.md、delivery/ |

1. 只改自己的文件。跨目录需求交给文件负责人处理，不在别人目录里代改。
2. P3 是唯一前端；P2 只通过 `qa.service.answer()` 向 P3 提供服务。P3 不导入 answer_builder、templates 等内部模块。
3. P2 / P3 / P5 通过 `load_table()` / `load_result()` 取数；P2 / P3 通过 `run_query()` 调用参数化只读模板。
4. PageRank、度、中介中心性在 P1 的 scripts/calculate_metrics.py 中计算。analysis/ 只做简单聚合；前端 NetworkX 只做布局。
5. P5 维护测试集，P2 用于自测，P3 只读演示。P2 / P3 都不能修改测试题。
6. 公共依赖、配置由 P1 维护。契约变更同步更新分工与 docs；新增全局配置先告知使用方。
7. `.github/`、`.gitignore`、本指南与分工 / 规划属于协作配置，变更在 PR 中说明，由团队确认。旧演示业务代码只读保留，兼容性修复由 P1 处理。
8. 不提交凭据、虚拟环境、原始 Excel、全量 Parquet、视频或压缩包。样例基础表和样例预计算结果入 Git，全量结果本地生成。

## 同步与提交

开工前 git fetch origin，将 origin/develop 合并到个人分支；不强推共享分支。个人分支 PR 目标选 develop。提交具体文件，避免把本地残留数据或其他人的改动一起提交。

新版创建 `p2-qa` 和 `p3-frontend`。旧 `p2-pages`、`p3-qa` 保留原提交，不自动删除、不重置。已在旧分支工作的同学应先保留本地提交，再把属于新职责的改动迁到新分支；不要将整条旧分支直接合并导致越界。

## 验证

```powershell
python -m compileall -q app.py core scripts pages analysis qa ui eval legacy
python -m eval.check_contracts
python -m eval.check_metrics
python -m eval.smoke_test
```

Actions 在 main / develop 推送及其 PR 上执行基础检查，无需数据库 / API。检查覆盖真实样例、指标计算口径、结果范围隔离、问答 mock/real 边界与页面入口；不是全量建图或真实问答准确率验收。

未设置服务端分支保护或 CODEOWNERS，成员账号尚未提供，文件所有权依协作流程执行。

## 资料与基线状态

- docs/团队分工.md 基于用户提供的 团队分工(1).md，修正过时的 Git 状态，并补充仓库接口细则。
- docs/项目规划.md 保留此前规划快照；人员与目录所有权以最新团队分工为准。
- 旧版验证结果只对应旧 Schema，不得当作新版评估。
- 本次为用户授权的公共基线迁移，后续按新版文件归属开发。全量导入、真实问答和业务验收仍待完成。
